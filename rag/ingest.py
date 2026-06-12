# -*-coding: utf-8 -*-
"""将 wiki / 原文灌入 SQLite，并构建向量索引。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from character_relations import (
    ALIASES,
    FACTIONS,
    RELATION_EDGES,
)
from rag import embeddings
from rag.config import (
    PLAIN_SOURCE,
    WIKI_CONCEPT,
    WIKI_ENTITY,
    WIKI_FACTION,
    WIKI_INDEX,
)
from rag.db import (
    CatalogNode,
    Chunk,
    Document,
    EntityAlias,
    RelationEdge,
    clear_corpus,
    get_session,
    init_db,
    meta_load,
    new_id,
)

CHAPTER_HEAD = re.compile(
    r"正文\s*(第[一二三四五六七八九十百零]+回)\s+([^\n]+)"
)


def _add_doc(
    session,
    doc_type: str,
    path: Path,
    title: str,
    content: str,
    meta: dict,
) -> str:
    doc_id = new_id()
    session.add(
        Document(
            id=doc_id,
            doc_type=doc_type,
            source_path=str(path),
            title=title,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    chunk_id = new_id()
    session.add(
        Chunk(
            id=chunk_id,
            document_id=doc_id,
            content=content,
            token_est=len(content),
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    return chunk_id


def ingest_catalog(session) -> None:
    index_md = WIKI_INDEX / "index.md"
    if index_md.exists():
        text = index_md.read_text(encoding="utf-8")
        session.add(
            CatalogNode(
                id=new_id(),
                node_type="index",
                title="三国演义知识库总索引",
                summary=text[:800],
                chapter_ordinal=None,
                source_path=str(index_md),
            )
        )
    for p in sorted((WIKI_INDEX / "parts").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        session.add(
            CatalogNode(
                id=new_id(),
                node_type="part",
                title=p.stem,
                summary=text[:600],
                chapter_ordinal=None,
                source_path=str(p),
            )
        )
    for p in sorted((WIKI_INDEX / "chapters").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.search(r"第(\d+)回|第([一二三四五六七八九十百零]+回)", p.stem)
        ordinal = None
        title = p.stem
        if text.startswith("# "):
            title = text.split("\n", 1)[0].lstrip("# ").strip()
        summary = ""
        if "## 摘要" in text:
            part = text.split("## 摘要", 1)[1].split("##", 1)[0].strip()
            summary = part[:500]
        session.add(
            CatalogNode(
                id=new_id(),
                node_type="chapter",
                title=title,
                summary=summary or text[:400],
                chapter_ordinal=ordinal,
                source_path=str(p),
            )
        )
        _add_doc(
            session,
            "chapter_summary",
            p,
            title,
            text,
            {"chapter": p.stem},
        )


def ingest_wiki_dir(session, directory: Path, doc_type: str) -> None:
    if not directory.exists():
        return
    for p in sorted(directory.glob("*.md")):
        if p.name in ("实体目录.md", "概念目录.md", "index.md"):
            continue
        text = p.read_text(encoding="utf-8")
        title = p.stem
        _add_doc(session, doc_type, p, title, text, {"name": title})


def ingest_raw_chapters(session) -> list[str]:
    """按回切分原文，大块再切分为约 500 字段落。"""
    if not PLAIN_SOURCE.exists():
        return []
    raw = PLAIN_SOURCE.read_text(encoding="utf-8")
    raw = re.sub(r"分节阅读\s*\d+\s*\n", "\n", raw)
    matches = list(CHAPTER_HEAD.finditer(raw))
    chunk_ids: list[str] = []
    max_chunk = 520

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end() : end].strip()
        label = m.group(1)
        title = m.group(2).strip()
        plain = re.sub(r"\s+", "", body)
        parts = [
            plain[j : j + max_chunk]
            for j in range(0, len(plain), max_chunk - 80)
        ]
        for pi, part in enumerate(parts):
            if len(part) < 30:
                continue
            cid = _add_doc(
                session,
                "raw_chunk",
                PLAIN_SOURCE,
                f"{label}·{title}({pi + 1})",
                part,
                {"chapter": label, "part": pi},
            )
            chunk_ids.append(cid)
    return chunk_ids


def ingest_relations(session) -> None:
    for alias, canonical in ALIASES.items():
        session.merge(EntityAlias(alias=alias, canonical=canonical))
    for x, y, tags in RELATION_EDGES:
        session.add(
            RelationEdge(
                id=new_id(),
                from_entity=x,
                to_entity=y,
                tags_json=json.dumps(tags, ensure_ascii=False),
            )
        )


def run_ingest(*, build_vectors: bool = True) -> dict:
    init_db()
    session = get_session()
    clear_corpus(session)

    ingest_relations(session)
    ingest_catalog(session)
    ingest_wiki_dir(session, WIKI_ENTITY, "entity")
    ingest_wiki_dir(session, WIKI_CONCEPT, "concept")
    ingest_wiki_dir(session, WIKI_FACTION, "faction")
    raw_ids = ingest_raw_chapters(session)
    session.commit()

    from sqlalchemy import select

    chunks = list(session.scalars(select(Chunk)).all())
    all_ids = [c.id for c in chunks]
    texts = [c.content for c in chunks]

    if build_vectors and texts:
        matrix = embeddings.embed_texts(texts)
        embeddings.save_embedding_index(all_ids, matrix)

    session.close()
    return {
        "chunks": len(all_ids),
        "raw_chapter_parts": len(raw_ids),
        "factions": len(FACTIONS),
    }


if __name__ == "__main__":
    stats = run_ingest()
    print("灌库完成:", stats)
