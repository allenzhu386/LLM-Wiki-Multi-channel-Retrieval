# -*-coding: utf-8 -*-
"""CoT 检索路由：选择 catalog / graph / hybrid 及参数。"""

from __future__ import annotations

from typing import Any

from rag.config import (
    DEFAULT_HYBRID_TOP_K,
    DEFAULT_RERANK_TOP_N,
    HYBRID_ALPHA,
    QWEN_MODEL_ROUTER,
)
from rag.llm import chat_json

ROUTER_SYSTEM = """你是《三国演义》知识库检索路由器。根据用户问题，先简短分析（reasoning），再输出 JSON（不要其它文字）：
{
  "reasoning": "分析过程",
  "paths": {
    "catalog": {"enabled": true/false},
    "graph": {"enabled": true/false, "seed_entities": ["刘备"], "hops": 1},
    "hybrid": {"enabled": true/false, "top_k": 40, "alpha": 0.55, "entity_filter": []}
  },
  "rerank_top_n": 6
}
规则：
- 问第几回、目录、概览 -> catalog=true
- 问人物关系、阵营、两人为何 -> graph=true，填 seed_entities
- 问情节、细节、原文 -> hybrid=true，必须给 top_k（30-50）
- 可多条同时为 true
- 复合问题多路开启"""


def default_plan() -> dict[str, Any]:
    return {
        "reasoning": "默认：混合检索为主，图谱与目录辅助",
        "paths": {
            "catalog": {"enabled": False},
            "graph": {"enabled": True, "seed_entities": [], "hops": 1},
            "hybrid": {
                "enabled": True,
                "top_k": DEFAULT_HYBRID_TOP_K,
                "alpha": HYBRID_ALPHA,
                "entity_filter": [],
            },
        },
        "rerank_top_n": DEFAULT_RERANK_TOP_N,
    }


def route_query(query: str) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM},
        {"role": "user", "content": query},
    ]
    try:
        plan = chat_json(messages, model=QWEN_MODEL_ROUTER)
        if "paths" not in plan:
            return default_plan()
        return plan
    except Exception:
        return default_plan()
