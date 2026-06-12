# -*-coding: utf-8 -*-
"""三国演义 RAG 问答 API。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag.db import DB_PATH, init_db
from rag.ingest import run_ingest
from rag.pipeline import ask

app = FastAPI(title="三国演义知识问答")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = ROOT / "web"
ASSETS_DIR = WEB_DIR / "assets"


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class IngestRequest(BaseModel):
    build_vectors: bool = True


@app.on_event("startup")
def startup() -> None:
    init_db()
    # 启动时校验 DashScope（读取系统环境变量，无需虚拟环境）
    try:
        from rag.llm import ensure_api_key

        ensure_api_key()
    except RuntimeError as e:
        import logging

        logging.getLogger("uvicorn.error").warning("DashScope: %s", e)


@app.get("/")
def index_page():
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "请访问 /web/index.html"}


@app.get("/config.js")
def config_js():
    path = WEB_DIR / "config.js"
    if path.exists():
        return FileResponse(path, media_type="application/javascript")
    from fastapi.responses import Response

    return Response(
        content='window.API_BASE = "";',
        media_type="application/javascript",
    )


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.query.strip():
        return JSONResponse(status_code=400, content={"detail": "问题不能为空"})
    try:
        return ask(req.query.strip(), req.session_id, stream=False)
    except UnicodeEncodeError:
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "DASHSCOPE_API_KEY 格式错误：密钥不能包含中文。"
                    "请执行 export DASHSCOPE_API_KEY=sk-开头的英文密钥 后重启服务。"
                )
            },
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.post("/api/ingest")
def ingest(req: IngestRequest):
    try:
        stats = run_ingest(build_vectors=req.build_vectors)
        return {"ok": True, "stats": stats, "db": str(DB_PATH)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.get("/api/health")
def health():
    return {"ok": True, "db_exists": DB_PATH.exists()}


if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")
