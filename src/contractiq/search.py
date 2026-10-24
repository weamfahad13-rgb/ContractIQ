"""Retrieval: vector search, keyword search, Reciprocal Rank Fusion, and reranking."""

from dataclasses import dataclass
from typing import Literal

from contractiq.db import connect
from contractiq.models import embed, rerank_scores

Mode = Literal["vector", "hybrid", "rerank"]

CANDIDATES = 20  # how many results each search contributes before fusion / reranking
RRF_K = 60


@dataclass
class Hit:
    chunk_id: int
    contract_id: int
    contract_title: str
    heading: str
    text: str
    start_char: int
    end_char: int
    score: float


_SELECT = """
    SELECT ch.id, ch.contract_id, c.title, ch.heading, ch.text, ch.start_char, ch.end_char
    FROM chunks ch JOIN contracts c ON c.id = ch.contract_id
"""


def _scope(contract_id: int | None) -> tuple[str, tuple]:
    return ("AND ch.contract_id = %s", (contract_id,)) if contract_id else ("", ())


def vector_search(conn, query: str, k: int, contract_id: int | None = None) -> list[Hit]:
    where, args = _scope(contract_id)
    rows = conn.execute(
        f"""{_SELECT} WHERE ch.embedding IS NOT NULL {where}
            ORDER BY ch.embedding <=> %s LIMIT %s""",
        (*args, embed([query])[0], k),
    ).fetchall()
    return [Hit(*r, score=1 / (i + 1)) for i, r in enumerate(rows)]


def keyword_search(conn, query: str, k: int, contract_id: int | None = None) -> list[Hit]:
    where, args = _scope(contract_id)
    # plainto_tsquery ANDs every word, which almost never matches a full question,
    # so turn it into an OR query and let ts_rank_cd reward chunks matching more terms.
    # The 'english' query matches stemmed English chunks, the 'simple' one matches Arabic chunks.
    rows = conn.execute(
        f"""WITH q AS (
                SELECT replace(plainto_tsquery('english', %s)::text, '&', '|') AS en,
                       replace(plainto_tsquery('simple', %s)::text, '&', '|') AS ar
            ), tq AS (
                SELECT CASE WHEN en = '' THEN NULL ELSE en::tsquery END AS en,
                       CASE WHEN ar = '' THEN NULL ELSE ar::tsquery END AS ar
                FROM q
            )
            SELECT ch.id, ch.contract_id, c.title, ch.heading, ch.text, ch.start_char, ch.end_char
            FROM chunks ch JOIN contracts c ON c.id = ch.contract_id, tq
            WHERE (ch.tsv @@ tq.en OR ch.tsv @@ tq.ar) {where}
            ORDER BY coalesce(ts_rank_cd(ch.tsv, tq.en), 0) + coalesce(ts_rank_cd(ch.tsv, tq.ar), 0) DESC
            LIMIT %s""",
        (query, query, *args, k),
    ).fetchall()
    return [Hit(*r, score=1 / (i + 1)) for i, r in enumerate(rows)]


def rrf(*ranked_lists: list[Hit]) -> list[Hit]:
    """Reciprocal Rank Fusion: score = sum of 1 / (k + rank) over the lists a chunk appears in."""
    fused: dict[int, Hit] = {}
    for hits in ranked_lists:
        for rank, h in enumerate(hits, start=1):
            if h.chunk_id not in fused:
                fused[h.chunk_id] = Hit(**{**h.__dict__, "score": 0.0})
            fused[h.chunk_id].score += 1 / (RRF_K + rank)
    return sorted(fused.values(), key=lambda h: h.score, reverse=True)


def retrieve(query: str, k: int = 5, mode: Mode = "rerank", contract_id: int | None = None,
             conn=None) -> list[Hit]:
    own = conn is None
    conn = conn or connect()
    try:
        if mode == "vector":
            return vector_search(conn, query, k, contract_id)

        fused = rrf(vector_search(conn, query, CANDIDATES, contract_id),
                    keyword_search(conn, query, CANDIDATES, contract_id))
        if mode == "hybrid":
            return fused[:k]

        candidates = fused[:CANDIDATES]
        scores = rerank_scores(query, [f"{h.heading}\n{h.text}" for h in candidates])
        for h, s in zip(candidates, scores):
            h.score = s
        return sorted(candidates, key=lambda h: h.score, reverse=True)[:k]
    finally:
        if own:
            conn.close()
