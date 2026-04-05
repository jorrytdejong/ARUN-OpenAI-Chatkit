"""SQLAlchemy ORM models for app persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CustomerAccess(Base):
    __tablename__ = "customer_access"

    auth0_user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_status: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    has_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


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
