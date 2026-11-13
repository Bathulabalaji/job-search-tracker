"""provider usage ledger for the AI assistant

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "provider_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("task", sa.String(length=40), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_provider_usage_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_usage_events")),
    )
    op.create_index(
        "ix_provider_usage_events_resource_created",
        "provider_usage_events",
        ["resource", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_usage_events_user_created",
        "provider_usage_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "provider_resource_state",
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("minute_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minute_requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minute_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("day_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day_requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("day_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reported_remaining_requests", sa.Integer(), nullable=True),
        sa.Column("reported_remaining_tokens", sa.Integer(), nullable=True),
        sa.Column("reported_requests_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported_tokens_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_reason", sa.String(length=40), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("circuit_state", sa.String(length=10), server_default="closed", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("resource", name=op.f("pk_provider_resource_state")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("provider_resource_state")
    op.drop_index("ix_provider_usage_events_user_created", table_name="provider_usage_events")
    op.drop_index("ix_provider_usage_events_resource_created", table_name="provider_usage_events")
    op.drop_table("provider_usage_events")
