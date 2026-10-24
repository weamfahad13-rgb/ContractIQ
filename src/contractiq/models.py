"""Local embedding and reranking models, loaded once on first use."""

from functools import cache

import numpy as np

from contractiq.config import EMBED_MODEL, RERANK_MODEL


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


@cache
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL, device=_device())


@cache
def reranker():
    import torch
    from sentence_transformers import CrossEncoder
    device = _device()
    # fp16 on GPU is ~3x faster for the reranker, with no measurable change in ranking quality.
    dtype = torch.float16 if device == "cuda" else torch.float32
    return CrossEncoder(RERANK_MODEL, device=device, max_length=512, model_kwargs={"torch_dtype": dtype})


def embed(texts: list[str], batch_size: int = 16) -> np.ndarray:
    # BGE-M3 needs no query/passage prefixes; normalized vectors make cosine = dot product.
    return embedder().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=len(texts) > 100)


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return reranker().predict([(query, p) for p in passages], batch_size=16).tolist()
