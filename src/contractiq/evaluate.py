"""Retrieval evaluation against CUAD's lawyer-labeled clause spans.

For every supply-chain contract and clause type that a lawyer found in it, ask a natural
question (in English and in Arabic) scoped to that contract, and check whether the top-k
chunks cover the labeled span.

    python -m contractiq.evaluate
"""

import json
import time
from datetime import datetime, timezone

from contractiq.config import DATA_DIR
from contractiq.cuad import load_supply_chain_contracts
from contractiq.db import connect
from contractiq.search import retrieve

K = 5
RESULTS = DATA_DIR / "eval" / "retrieval.json"

QUESTIONS = {
    "Governing Law": ("Which law governs this agreement?",
                      "ما القانون الذي يحكم هذه الاتفاقية؟"),
    "Expiration Date": ("When does this agreement expire?",
                        "متى تنتهي هذه الاتفاقية؟"),
    "Renewal Term": ("Does the agreement renew automatically, and for how long?",
                     "هل يتجدد العقد تلقائياً، ولأي مدة؟"),
    "Notice Period To Terminate Renewal": ("How much notice is needed to stop the agreement from renewing?",
                                           "كم مدة الإشعار المطلوبة لمنع تجديد العقد؟"),
    "Anti-Assignment": ("Can either party assign or transfer the agreement to someone else?",
                        "هل يحق لأي طرف التنازل عن العقد أو نقله لطرف آخر؟"),
    "Cap On Liability": ("Is there a cap or limit on liability?",
                         "هل يوجد حد أقصى للمسؤولية؟"),
    "Audit Rights": ("Does either party have the right to audit the other's books or records?",
                     "هل يحق لأحد الطرفين تدقيق سجلات أو دفاتر الطرف الآخر؟"),
    "Minimum Commitment": ("Is there a minimum purchase or order commitment?",
                           "هل يوجد حد أدنى ملزم للشراء أو الطلب؟"),
    "Insurance": ("What insurance must the parties maintain?",
                  "ما التأمين الذي يجب على الأطراف الاحتفاظ به؟"),
    "Warranty Duration": ("How long is the warranty period?",
                          "ما مدة الضمان؟"),
    "Termination For Convenience": ("Can a party terminate the agreement without cause?",
                                    "هل يحق لأحد الطرفين إنهاء العقد دون سبب؟"),
    "Exclusivity": ("Is there an exclusivity obligation?",
                    "هل يوجد التزام بالحصرية؟"),
}


def _covered(spans: list[tuple[int, int]], hits) -> bool:
    """A question is answered if the retrieved chunks cover at least half of any labeled span."""
    for s, e in spans:
        covered = sum(max(0, min(e, h.end_char) - max(s, h.start_char)) for h in hits)
        if covered >= 0.5 * (e - s):
            return True
    return False


def build_cases(conn) -> list[dict]:
    ids = dict(conn.execute("SELECT title, id FROM contracts WHERE source = 'cuad'").fetchall())
    cases = []
    for c in load_supply_chain_contracts():
        for label in c.labels:
            if label.category in QUESTIONS and label.spans:
                en, ar = QUESTIONS[label.category]
                cases.append({"contract_id": ids[c.title], "contract": c.title,
                              "category": label.category, "spans": label.spans, "en": en, "ar": ar})
    return cases


def run(conn, cases, mode: str, lang: str) -> dict:
    hits_at_k, rr, failures = 0, 0.0, []
    by_cat: dict[str, list[int]] = {}
    start = time.perf_counter()
    for case in cases:
        hits = retrieve(case[lang], k=K, mode=mode, contract_id=case["contract_id"], conn=conn)
        rank = next((i for i in range(1, len(hits) + 1) if _covered(case["spans"], hits[:i])), None)
        by_cat.setdefault(case["category"], []).append(1 if rank else 0)
        if rank:
            hits_at_k += 1
            rr += 1 / rank
        else:
            failures.append({"question": case[lang], "category": case["category"], "contract": case["contract"]})
    n = len(cases)
    return {"mode": mode, "lang": lang, "n": n,
            "recall_at_k": round(hits_at_k / n, 4), "mrr": round(rr / n, 4),
            "avg_latency_ms": round(1000 * (time.perf_counter() - start) / n, 1),
            "per_category": {c: round(sum(v) / len(v), 4) for c, v in sorted(by_cat.items())},
            "failures": failures[:25]}


def main() -> None:
    with connect() as conn:
        cases = build_cases(conn)
        print(f"{len(cases)} questions over {len({c['contract_id'] for c in cases})} contracts")
        # Load both models before timing anything, so the first run isn't charged for it.
        retrieve(cases[0]["en"], k=K, mode="rerank", contract_id=cases[0]["contract_id"], conn=conn)
        runs = []
        for mode in ("vector", "hybrid", "rerank", "fusion"):
            for lang in ("en", "ar"):
                r = run(conn, cases, mode, lang)
                runs.append(r)
                print(f"  {mode:7s} {lang}: Recall@{K} {r['recall_at_k']:.3f}  MRR {r['mrr']:.3f}  "
                      f"{r['avg_latency_ms']} ms/query")

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "k": K, "n_questions": len(cases), "categories": list(QUESTIONS), "runs": runs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
