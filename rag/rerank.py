# -*-coding: utf-8 -*-
"""对合并候选做精排（关键词重叠 + 可选 DashScope）。"""

from __future__ import annotations

import re

from rag.retrievers import RetrievedDoc


def rerank_docs(
    query: str,
    docs: list[RetrievedDoc],
    top_n: int,
) -> list[RetrievedDoc]:
    if not docs:
        return []
    q_chars = set(query)
    q_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", query))

    def score_doc(d: RetrievedDoc) -> float:
        text = d.content + d.title
        overlap = sum(1 for w in q_words if w in text)
        char_hit = sum(1 for c in q_chars if len(c.strip()) and c in text)
        base = d.score
        return base * 0.4 + overlap * 0.35 + char_hit * 0.01

    ranked = sorted(docs, key=score_doc, reverse=True)
    seen: set[str] = set()
    out: list[RetrievedDoc] = []
    for d in ranked:
        key = d.chunk_id
        if key in seen:
            continue
        seen.add(key)
        d.score = score_doc(d)
        out.append(d)
        if len(out) >= top_n:
            break
    return out
