"""SQLAlchemy ORM models for app persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ChatThreadRecord(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        Index("ix_chat_threads_auth0_user_created_at", "auth0_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    auth0_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    thread_json: Mapped[str] = mapped_column(Text, nullable=False)


class ChatItemRecord(Base):
    __tablename__ = "chat_items"
    __table_args__ = (
        Index("ix_chat_items_thread_created_at", "thread_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_json: Mapped[str] = mapped_column(Text, nullable=False)
