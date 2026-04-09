"""Add subscription ending state fields to customer access."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_01"
down_revision = "20250405_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_access",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "customer_access",
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_access",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_access", "ended_at")
    op.drop_column("customer_access", "cancellation_requested_at")
    op.drop_column("customer_access", "cancel_at_period_end")
