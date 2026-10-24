"""HTTP API for the frontend.

    uvicorn contractiq.api:app --reload
"""

import json
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from contractiq.config import DATA_DIR, ROOT
from contractiq.db import connect
from contractiq.llm import LLMNotConfigured, LLMRateLimited

app = FastAPI(title="ContractIQ")

EXPIRING_DAYS = 60


def status(end: date | None, today: date) -> str:
    if end is None:
        return "unknown"
    if end < today:
        return "expired"
    return "expiring_soon" if (end - today).days <= EXPIRING_DAYS else "active"


@app.get("/api/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


@app.get("/api/contracts")
def list_contracts():
    today = date.today()
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.supplier, c.contract_type, c.language, c.source,
                      c.start_date, c.end_date, count(ch.id)
               FROM contracts c LEFT JOIN chunks ch ON ch.contract_id = c.id
               GROUP BY c.id
               ORDER BY c.source DESC, c.end_date NULLS LAST, c.title"""
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "supplier": r[2], "contract_type": r[3], "language": r[4],
         "source": r[5], "start_date": r[6], "end_date": r[7], "chunks": r[8], "status": status(r[7], today)}
        for r in rows
    ]


@app.get("/api/contracts/{contract_id}")
def get_contract(contract_id: int):
    with connect() as conn:
        c = conn.execute(
            """SELECT id, title, supplier, contract_type, language, source, start_date, end_date, full_text
               FROM contracts WHERE id = %s""", (contract_id,)
        ).fetchone()
        if not c:
            raise HTTPException(404, "Contract not found")
        chunks = conn.execute(
            "SELECT id, ord, heading, start_char, end_char FROM chunks WHERE contract_id = %s ORDER BY ord",
            (contract_id,),
        ).fetchall()
    keys = ["id", "title", "supplier", "contract_type", "language", "source", "start_date", "end_date", "full_text"]
    return {**dict(zip(keys, c)),
            "chunks": [dict(zip(["id", "ord", "heading", "start_char", "end_char"], ch)) for ch in chunks]}


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    contract_id: int | None = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    from contractiq.rag import answer  # loads the embedding models on first use

    try:
        return answer(req.question, req.contract_id)
    except LLMNotConfigured as e:
        raise HTTPException(503, str(e))
    except LLMRateLimited as e:
        raise HTTPException(429, str(e))


@app.get("/api/evaluation")
def evaluation():
    out = {}
    for name in ("retrieval", "answers"):
        path = DATA_DIR / "eval" / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8"))
    return out


# Serve the built frontend from the same server, with SPA fallback for client-side routes.
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = (DIST / path).resolve()
        if path and file.is_file() and DIST.resolve() in file.parents:
            return FileResponse(file)
        # index.html points at hashed asset names, so it must never be served stale after a rebuild.
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
