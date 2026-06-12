# -*-coding: utf-8 -*-
"""DashScope 文本向量与本地 numpy 缓存。"""

from __future__ import annotations

import json
from typing import Sequence

import dashscope
import numpy as np
from dashscope import TextEmbedding

from rag.config import CHUNK_META_CACHE, EMBEDDING_CACHE, QWEN_EMBEDDING_MODEL

_batch_size = 25


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """返回 shape (n, dim) 的向量矩阵。"""
    from rag.llm import ensure_api_key

    ensure_api_key()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _batch_size):
        batch = list(texts[i : i + _batch_size])
        resp = TextEmbedding.call(model=QWEN_EMBEDDING_MODEL, input=batch)
        if resp.status_code != 200:
            raise RuntimeError(f"Embedding 失败: {resp.code} {resp.message}")
        for item in resp.output["embeddings"]:
            vectors.append(item["embedding"])
    return np.array(vectors, dtype=np.float32)


def save_embedding_index(chunk_ids: list[str], matrix: np.ndarray) -> None:
    EMBEDDING_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(EMBEDDING_CACHE, embeddings=matrix)
    CHUNK_META_CACHE.write_text(
        json.dumps(chunk_ids, ensure_ascii=False), encoding="utf-8"
    )


def load_embedding_index() -> tuple[list[str], np.ndarray] | None:
    if not EMBEDDING_CACHE.exists() or not CHUNK_META_CACHE.exists():
        return None
    data = np.load(EMBEDDING_CACHE)
    chunk_ids = json.loads(CHUNK_META_CACHE.read_text(encoding="utf-8"))
    return chunk_ids, data["embeddings"]


def cosine_top_k(
    query_vec: np.ndarray,
    matrix: np.ndarray,
    chunk_ids: list[str],
    k: int,
) -> list[tuple[str, float]]:
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
    sims = (matrix / norms) @ q
    idx = np.argsort(-sims)[:k]
    return [(chunk_ids[i], float(sims[i])) for i in idx]
