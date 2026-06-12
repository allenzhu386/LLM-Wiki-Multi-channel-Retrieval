# -*-coding: utf-8 -*-
"""SQLite 持久化：文档块、目录、关系、会话与检索日志。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from rag.config import DATA_DIR, DB_PATH


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    doc_type = Column(String(32), nullable=False)
    source_path = Column(String(512), nullable=False)
    title = Column(String(256), default="")
    meta_json = Column(Text, default="{}")
    chunks = relationship("Chunk", back_populates="document")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    token_est = Column(Integer, default=0)
    meta_json = Column(Text, default="{}")
    document = relationship("Document", back_populates="chunks")


class CatalogNode(Base):
    __tablename__ = "catalog_nodes"

    id = Column(String(36), primary_key=True)
    node_type = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    summary = Column(Text, default="")
    chapter_ordinal = Column(Integer, nullable=True)
    source_path = Column(String(512), default="")


class RelationEdge(Base):
    __tablename__ = "relation_edges"

    id = Column(String(36), primary_key=True)
    from_entity = Column(String(64), nullable=False)
    to_entity = Column(String(64), nullable=False)
    tags_json = Column(Text, default="[]")


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    alias = Column(String(64), primary_key=True)
    canonical = Column(String(64), nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    trace_json = Column(Text, default="{}")
    session = relationship("ChatSession", back_populates="messages")


def _engine():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


engine = _engine()
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)


def new_id() -> str:
    return str(uuid.uuid4())


def meta_load(row: str) -> dict:
    return json.loads(row or "{}")


def get_session() -> Session:
    return SessionLocal()


def clear_corpus(session: Session) -> None:
    session.execute(text("DELETE FROM chunks"))
    session.execute(text("DELETE FROM documents"))
    session.execute(text("DELETE FROM catalog_nodes"))
    session.execute(text("DELETE FROM relation_edges"))
    session.execute(text("DELETE FROM entity_aliases"))
    session.commit()


def save_retrieval_trace(
    session: Session,
    message_id: str,
    trace: dict[str, Any],
) -> None:
    msg = session.get(ChatMessage, message_id)
    if msg:
        msg.trace_json = json.dumps(trace, ensure_ascii=False)
        session.commit()
