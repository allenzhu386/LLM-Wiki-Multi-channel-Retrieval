# -*-coding: utf-8 -*-
"""RAG 系统路径与模型配置。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "rag.db"
EMBEDDING_CACHE = DATA_DIR / "embeddings.npz"
CHUNK_META_CACHE = DATA_DIR / "chunk_ids.json"

PLAIN_SOURCE = ROOT / "source" / "three_kingdoms.txt.plain.bak"
WIKI_INDEX = ROOT / "wiki" / "index"
WIKI_ENTITY = ROOT / "wiki" / "entity" / "entity"
WIKI_CONCEPT = ROOT / "wiki" / "concept" / "concept"
WIKI_FACTION = ROOT / "wiki" / "faction"

# DashScope 模型（与 1-情感分析-Qwen.py 一致用 Generation.call）
QWEN_MODEL_ROUTER = "qwen-turbo"
QWEN_MODEL_GENERATOR = "qwen-plus"
QWEN_EMBEDDING_MODEL = "text-embedding-v2"

DEFAULT_HYBRID_TOP_K = 40
DEFAULT_RERANK_TOP_N = 6
HYBRID_ALPHA = 0.55
