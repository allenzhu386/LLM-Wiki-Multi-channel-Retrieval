# -*-coding: utf-8 -*-
"""三路检索：目录、图谱链接、混合（向量+BM25）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from character_relations import ALIASES, normalize_character_name
from rag import embeddings
from rag.config import DEFAULT_HYBRID_TOP_K, HYBRID_ALPHA
from rag.db import CatalogNode, Chunk, EntityAlias, RelationEdge, meta_load


@dataclass
class RetrievedDoc:
    chunk_id: str
    content: str
    title: str
    source_path: str
    doc_type: str
    score: float
    via: str
    extra: dict = field(default_factory=dict)


def _chunk_to_doc(
    chunk: Chunk,
    doc_title: str,
    source_path: str,
    doc_type: str,
    score: float,
    via: str,
    **extra,
) -> RetrievedDoc:
    meta = meta_load(chunk.meta_json)
    return RetrievedDoc(
        chunk_id=chunk.id,
        content=chunk.content,
        title=doc_title or meta.get("chapter", ""),
        source_path=source_path,
        doc_type=doc_type,
        score=score,
        via=via,
        extra=extra,
    )


def extract_entities(query: str, session: Session) -> list[str]:
    found: list[str] = []
    aliases = list(session.scalars(select(EntityAlias)).all())
    text = query
    pairs = sorted(
        [(a.alias, a.canonical) for a in aliases],
        key=lambda x: len(x[0]),
        reverse=True,
    )
    used: set[str] = set()
    for alias, canonical in pairs:
        if alias in text and canonical not in used:
            found.append(canonical)
            used.add(canonical)
    return found


def retrieve_catalog(session: Session, query: str, limit: int = 5) -> list[RetrievedDoc]:
    nodes = list(session.scalars(select(CatalogNode)).all())
    q = query.lower()
    scored: list[tuple[float, CatalogNode]] = []
    for n in nodes:
        score = 0.0
        if n.title and n.title in query:
            score += 3
        if n.summary and any(w in n.summary for w in query if len(w) > 1):
            score += 1
        m = re.search(r"第([一二三四五六七八九十百零]+)回", query)
        if m and m.group(1) in n.title:
            score += 5
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda x: -x[0])
    out: list[RetrievedDoc] = []
    for score, n in scored[:limit]:
        content = f"【{n.node_type}】{n.title}\n{n.summary}"
        out.append(
            RetrievedDoc(
                chunk_id=f"catalog:{n.id}",
                content=content,
                title=n.title,
                source_path=n.source_path,
                doc_type="catalog",
                score=score,
                via="catalog",
            )
        )
    if not out and nodes:
        for n in nodes[:3]:
            if n.node_type == "index":
                out.append(
                    RetrievedDoc(
                        chunk_id=f"catalog:{n.id}",
                        content=n.summary[:600],
                        title=n.title,
                        source_path=n.source_path,
                        doc_type="catalog",
                        score=0.1,
                        via="catalog",
                    )
                )
    return out


def retrieve_graph(
    session: Session,
    query: str,
    seed_entities: list[str] | None = None,
    hops: int = 1,
) -> list[RetrievedDoc]:
    seeds = seed_entities or extract_entities(query, session)
    if not seeds:
        return []

    edges = list(session.scalars(select(RelationEdge)).all())
    related: set[str] = set(seeds)
    lines: list[str] = []
    for e in edges:
        tags = json.loads(e.tags_json or "[]")
        lab = "；".join(tags)
        if e.from_entity in related or e.to_entity in related:
            lines.append(f"[[{e.from_entity}]] ↔ [[{e.to_entity}]]：{lab}")
            related.add(e.from_entity)
            related.add(e.to_entity)

    out: list[RetrievedDoc] = []
    if lines:
        out.append(
            RetrievedDoc(
                chunk_id="graph:relations",
                content="人物关系：\n" + "\n".join(lines[:20]),
                title="结构化人物关系",
                source_path="character_relations.py",
                doc_type="graph",
                score=1.0,
                via="graph",
                extra={"entities": list(related)},
            )
        )

    from rag.db import Document

    for name in list(related)[:12]:
        doc = session.scalars(
            select(Document).where(
                Document.title == name, Document.doc_type == "entity"
            )
        ).first()
        if doc and doc.chunks:
            c = doc.chunks[0]
            out.append(
                _chunk_to_doc(
                    c,
                    doc.title,
                    doc.source_path,
                    doc.doc_type,
                    0.9,
                    "graph",
                    entity=name,
                )
            )
    return out


class HybridIndex:
    """内存 BM25 + 持久化向量。"""

    def __init__(self, session: Session):
        self.session = session
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []
        self._chunks: list[Chunk] = []
        self._embed_ids: list[str] | None = None
        self._embed_matrix: np.ndarray | None = None
        self._build()

    def _build(self) -> None:
        self._chunks = list(self.session.scalars(select(Chunk)).all())
        self._chunk_ids = [c.id for c in self._chunks]
        tokenized = [list(c.content) for c in self._chunks]
        if tokenized:
            self._bm25 = BM25Okapi(tokenized)
        loaded = embeddings.load_embedding_index()
        if loaded:
            self._embed_ids, self._embed_matrix = loaded

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_HYBRID_TOP_K,
        alpha: float = HYBRID_ALPHA,
        entity_filter: list[str] | None = None,
    ) -> list[RetrievedDoc]:
        if not self._chunks or not self._bm25:
            return []

        id_to_idx = {cid: i for i, cid in enumerate(self._chunk_ids)}
        scores = np.zeros(len(self._chunk_ids), dtype=np.float64)

        bm = np.array(self._bm25.get_scores(list(query)), dtype=np.float64)
        if bm.max() > 0:
            bm = bm / bm.max()
        scores += (1 - alpha) * bm

        if self._embed_matrix is not None and self._embed_ids:
            qv = embeddings.embed_texts([query])[0]
            id_map = {cid: i for i, cid in enumerate(self._embed_ids)}
            dense = np.zeros(len(self._chunk_ids))
            for i, cid in enumerate(self._chunk_ids):
                if cid in id_map:
                    idx = id_map[cid]
                    vec = self._embed_matrix[idx]
                    dense[i] = float(
                        np.dot(vec, qv)
                        / (np.linalg.norm(vec) * np.linalg.norm(qv) + 1e-9)
                    )
            if dense.max() > 0:
                dense /= dense.max()
            scores += alpha * dense

        if entity_filter:
            for i, c in enumerate(self._chunks):
                if not any(e in c.content for e in entity_filter):
                    scores[i] *= 0.3

        top_idx = np.argsort(-scores)[:top_k]
        from rag.db import Document

        out: list[RetrievedDoc] = []
        for i in top_idx:
            if scores[i] <= 0:
                continue
            c = self._chunks[i]
            doc = self.session.get(Document, c.document_id)
            out.append(
                _chunk_to_doc(
                    c,
                    doc.title if doc else "",
                    doc.source_path if doc else "",
                    doc.doc_type if doc else "",
                    float(scores[i]),
                    "hybrid",
                )
            )
        return out


def retrieve_hybrid(
    session: Session,
    query: str,
    top_k: int,
    alpha: float,
    entity_filter: list[str] | None,
    index: HybridIndex | None = None,
) -> list[RetrievedDoc]:
    idx = index or HybridIndex(session)
    return idx.search(query, top_k=top_k, alpha=alpha, entity_filter=entity_filter)
