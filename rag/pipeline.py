# -*-coding: utf-8 -*-
"""问答流水线：路由 -> 多路检索 -> 合并 -> Rerank -> 生成。"""

from __future__ import annotations

import json
from typing import Any, Generator

from rag.config import QWEN_MODEL_GENERATOR
from rag.db import ChatMessage, ChatSession, get_session, init_db, new_id, save_retrieval_trace
from rag.llm import chat_text, ensure_api_key, get_response
from rag.rerank import rerank_docs
from rag.retrievers import (
    HybridIndex,
    RetrievedDoc,
    extract_entities,
    retrieve_catalog,
    retrieve_graph,
    retrieve_hybrid,
)
from rag.router import route_query

GENERATOR_SYSTEM = """你是《三国演义》知识助手。仅依据用户提供的「检索材料」回答，不得编造。
要求：
1. 回答简洁准确，重要情节注明回目或来源。
2. 文末列出「参考来源」编号。
3. 材料不足时明确说「原文未检索到足够依据」。"""

# 与参考知识库项目一致：R1 混合 / R2 实体图谱 / R3 目录
VIA_TO_ROUTE: dict[str, str] = {
    "hybrid": "R1",
    "graph": "R2",
    "catalog": "R3",
}


def _merge_docs(lists: list[list[RetrievedDoc]]) -> list[RetrievedDoc]:
    merged: dict[str, RetrievedDoc] = {}
    routes: dict[str, list[str]] = {}
    for docs in lists:
        for d in docs:
            rid = VIA_TO_ROUTE.get(d.via, d.via)
            if d.chunk_id not in routes:
                routes[d.chunk_id] = []
            if rid not in routes[d.chunk_id]:
                routes[d.chunk_id].append(rid)
            if d.chunk_id not in merged or d.score > merged[d.chunk_id].score:
                merged[d.chunk_id] = d
    for cid, doc in merged.items():
        doc.extra["retrieved_by"] = routes.get(cid, [VIA_TO_ROUTE.get(doc.via, "R1")])
        doc.extra["hybrid_score"] = float(doc.score)
    return sorted(merged.values(), key=lambda x: -x.score)


def _display_similarity(scores: list[float], score: float) -> float:
    """将候选内相对分数映射为 28–99 的展示相关度（与参考项目一致）。"""
    if not scores:
        return round(float(score) * 100, 1)
    max_s = max(scores) or 1.0
    if max_s <= 0:
        return 0.0
    return round(min(99.9, (score / max_s) * 72 + 28), 1)


def _format_context(docs: list[RetrievedDoc]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        parts.append(
            f"[{i}] ({d.via}/{d.doc_type}) {d.title}\n"
            f"路径: {d.source_path}\n{d.content[:1200]}"
        )
    return "\n\n".join(parts)


def run_retrieval(session, query: str, plan: dict) -> tuple[list[RetrievedDoc], dict]:
    paths = plan.get("paths", {})
    all_lists: list[list[RetrievedDoc]] = []
    trace: dict[str, Any] = {"plan": plan, "steps": []}

    if paths.get("catalog", {}).get("enabled"):
        cat = retrieve_catalog(session, query)
        all_lists.append(cat)
        trace["steps"].append({"catalog": len(cat)})

    graph_cfg = paths.get("graph", {})
    if graph_cfg.get("enabled"):
        seeds = graph_cfg.get("seed_entities") or extract_entities(query, session)
        g = retrieve_graph(
            session,
            query,
            seed_entities=seeds,
            hops=graph_cfg.get("hops", 1),
        )
        all_lists.append(g)
        trace["steps"].append({"graph": len(g), "seeds": seeds})

    hybrid_cfg = paths.get("hybrid", {})
    if hybrid_cfg.get("enabled", True):
        top_k = int(hybrid_cfg.get("top_k", 40))
        alpha = float(hybrid_cfg.get("alpha", 0.55))
        ef = hybrid_cfg.get("entity_filter") or None
        idx = HybridIndex(session)
        h = retrieve_hybrid(session, query, top_k, alpha, ef, index=idx)
        all_lists.append(h)
        trace["steps"].append({"hybrid": len(h), "top_k": top_k})

    merged = _merge_docs(all_lists)
    top_n = int(plan.get("rerank_top_n", 6))
    final = rerank_docs(query, merged, top_n)
    rerank_scores = [d.score for d in final]
    trace["final_count"] = len(final)
    trace["citations"] = []
    for d in final:
        retrieved_by = d.extra.get("retrieved_by", [VIA_TO_ROUTE.get(d.via, "R1")])
        primary = retrieved_by[0] if len(retrieved_by) == 1 else "组合"
        trace["citations"].append(
            {
                "chunk_id": d.chunk_id,
                "title": d.title,
                "via": d.via,
                "route": primary,
                "retrieved_by": retrieved_by,
                "doc_type": d.doc_type,
                "source_path": d.source_path,
                "score": d.score,
                "hybrid_score": d.extra.get("hybrid_score", d.score),
                "similarity": _display_similarity(rerank_scores, d.score),
                "content": d.content[:800],
            }
        )
    enabled = []
    if paths.get("hybrid", {}).get("enabled", True):
        enabled.append("R1")
    if paths.get("graph", {}).get("enabled"):
        enabled.append("R2")
    if paths.get("catalog", {}).get("enabled"):
        enabled.append("R3")
    trace["enabled_routes"] = enabled
    return final, trace


def generate_answer(query: str, docs: list[RetrievedDoc]) -> str:
    ctx = _format_context(docs)
    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {
            "role": "user",
            "content": f"检索材料：\n{ctx}\n\n用户问题：{query}",
        },
    ]
    return chat_text(messages, model=QWEN_MODEL_GENERATOR)


def generate_answer_stream(
    query: str, docs: list[RetrievedDoc]
) -> Generator[str, None, None]:
    text = generate_answer(query, docs)
    yield text


def ask(
    query: str,
    session_id: str | None = None,
    *,
    stream: bool = False,
) -> dict[str, Any]:
    init_db()
    ensure_api_key()
    db = get_session()

    if not session_id:
        sid = new_id()
        db.add(ChatSession(id=sid))
        db.commit()
        session_id = sid

    user_msg = ChatMessage(
        id=new_id(),
        session_id=session_id,
        role="user",
        content=query,
    )
    db.add(user_msg)
    db.commit()

    plan = route_query(query)
    docs, trace = run_retrieval(db, query, plan)

    if stream:
        answer_parts: list[str] = []
        for piece in generate_answer_stream(query, docs):
            answer_parts.append(piece)
        answer = "".join(answer_parts)
    else:
        answer = generate_answer(query, docs)

    asst_id = new_id()
    asst_msg = ChatMessage(
        id=asst_id,
        session_id=session_id,
        role="assistant",
        content=answer,
    )
    db.add(asst_msg)
    db.commit()
    save_retrieval_trace(db, asst_id, trace)

    result = {
        "session_id": session_id,
        "message_id": asst_id,
        "answer": answer,
        "citations": trace.get("citations", []),
        "router": plan,
        "enabled_routes": trace.get("enabled_routes", []),
    }
    db.close()
    return result
