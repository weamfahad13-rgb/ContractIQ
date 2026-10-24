"""Answer-level evaluation with an LLM judge (needs GEMINI_API_KEY).

Runs the full pipeline on a sample of questions and asks a second model to grade:
- faithfulness: share of the answer's claims supported by the sources it was given
- relevance: whether the answer addresses the question

    python -m contractiq.evaluate_answers
"""

import json
import random
import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from contractiq.config import DATA_DIR
from contractiq.db import connect
from contractiq.evaluate import build_cases
from contractiq.llm import LLMRateLimited, generate
from contractiq.rag import answer
from contractiq.synthetic import SUPPLIERS

RESULTS = DATA_DIR / "eval" / "answers.json"
PROGRESS = DATA_DIR / "eval" / "answers_progress.json"
NOT_FOUND = re.compile(
    r"do(es)? not (contain|specify|mention|include)|not (specified|mentioned|available)|no information"
    r"|لا تحتوي|لا تتضمن|لم يرد|لا توجد معلومات|غير متوفر", re.IGNORECASE)
N_CUAD = 16  # keeps the run inside the free-tier daily quota

SAMPLE_QUESTIONS = [
    f"What is the late delivery penalty for {SUPPLIERS[0].name}?",
    f"ما غرامة التأخير في التسليم في عقد {SUPPLIERS[1].name_ar}؟",
    f"When does the {SUPPLIERS[3].name} agreement expire?",
    f"هل يتجدد عقد {SUPPLIERS[2].name_ar} تلقائياً؟",
    f"How many {SUPPLIERS[4].name} orders were delivered late?",
    f"What is the total value of purchase orders placed with {SUPPLIERS[0].name} in 2026?",
    f"Can we terminate the {SUPPLIERS[6].name} contract without cause, and with how much notice?",
    f"ما هو الحد الأدنى للالتزام السنوي مع {SUPPLIERS[5].name_ar}؟",
]


class Grade(BaseModel):
    faithfulness: float = Field(ge=0, le=1, description="Share of the answer's claims supported by the sources/data")
    relevant: bool
    reason: str


JUDGE_PROMPT = """You are grading a contract assistant. Judge ONLY against the sources and data shown.
Question: {q}
Sources:
{sources}
Database result: {data}
Answer: {a}
faithfulness = fraction of factual claims in the answer that the sources or data support
(an honest "not found" answer counts as faithful). relevant = the answer addresses the question."""


def grade(conn, result: dict) -> Grade:
    chunks = {c["chunk_id"]: c for c in result["citations"]}
    texts = dict(conn.execute("SELECT id, text FROM chunks WHERE id = ANY(%s)", (list(chunks),)).fetchall())
    sources = "\n".join(f"[{c['n']}] {texts.get(cid, '')}" for cid, c in chunks.items()) or "(none)"
    data = json.dumps(result["data"], ensure_ascii=False)[:3000] if result["data"] else "(none)"
    return generate(JUDGE_PROMPT.format(q=result["question"], sources=sources, data=data, a=result["answer"]),
                    fast=True, schema=Grade)  # separate free-tier quota from the answer model


def main() -> None:
    rng = random.Random(7)
    with connect() as conn:
        cases = build_cases(conn)
        sampled = rng.sample(cases, N_CUAD)
        questions = [(c[rng.choice(["en", "ar"])], c["contract_id"]) for c in sampled]
        questions += [(q, None) for q in SAMPLE_QUESTIONS]

        # The free tier allows only a few dozen calls a day, so progress is saved after every
        # question and a re-run picks up where the last one stopped.
        # Keyed by question AND contract: the same question is asked of several contracts.
        key = lambda q, cid: f"{cid}|{q}"
        saved = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else []
        done = {key(s["question"], s["contract_id"]): s for s in saved}
        for q, cid in questions:
            if key(q, cid) in done:
                continue
            try:
                t0 = time.perf_counter()
                result = answer(q, cid)
                latency = time.perf_counter() - t0
                g = grade(conn, result)
            except LLMRateLimited:
                print(f"Quota used up after {len(done)}/{len(questions)} questions; run again later to continue.")
                break
            done[key(q, cid)] = {"question": q, "contract_id": cid, "answer": result["answer"], "route": result["route"],
                       "faithfulness": g.faithfulness, "relevant": g.relevant, "reason": g.reason,
                       "latency_ms": round(latency * 1000)}
            PROGRESS.parent.mkdir(parents=True, exist_ok=True)
            PROGRESS.write_text(json.dumps(list(done.values()), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {g.faithfulness:.2f} {'✓' if g.relevant else '✗'}  {q[:70]}")

    samples = [done[key(q, cid)] for q, cid in questions if key(q, cid) in done]
    if len(samples) < len(questions):
        return
    n = len(samples)
    # Faithfulness can't tell "correct" from "honestly said not found". Every CUAD question here asks
    # about a clause a lawyer labeled, so a not-found answer there is a miss.
    cuad = [s for s in samples if s["contract_id"] is not None]
    missed = [s for s in cuad if NOT_FOUND.search(s["answer"])]
    summary = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": n,
        "faithfulness": round(sum(s["faithfulness"] for s in samples) / n, 4),
        "relevance": round(sum(s["relevant"] for s in samples) / n, 4),
        "not_found_rate": round(len(missed) / len(cuad), 4) if cuad else None,
        "avg_latency_ms": round(sum(s["latency_ms"] for s in samples) / n),
        "samples": samples,
    }
    RESULTS.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"faithfulness {summary['faithfulness']:.3f}  relevance {summary['relevance']:.3f}  -> {RESULTS}")


if __name__ == "__main__":
    main()
