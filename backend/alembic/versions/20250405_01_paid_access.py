"""Add persistent chat and customer access tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250405_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_access",
        sa.Column("auth0_user_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_status", sa.String(length=64), nullable=True),
        sa.Column("has_access", sa.Boolean(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("auth0_user_id"),
        sa.UniqueConstraint("stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_table(
        "stripe_webhook_events",
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("stripe_event_id"),
    )
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("auth0_user_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("thread_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_threads_auth0_user_created_at",
        "chat_threads",
        ["auth0_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_threads_auth0_user_id",
        "chat_threads",
        ["auth0_user_id"],
        unique=False,
    )
    op.create_table(
        "chat_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_items_thread_created_at",
        "chat_items",
        ["thread_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_items_thread_created_at", table_name="chat_items")
    op.drop_table("chat_items")
    op.drop_index("ix_chat_threads_auth0_user_id", table_name="chat_threads")
    op.drop_index("ix_chat_threads_auth0_user_created_at", table_name="chat_threads")
    op.drop_table("chat_threads")
    op.drop_table("stripe_webhook_events")
    op.drop_table("customer_access")
