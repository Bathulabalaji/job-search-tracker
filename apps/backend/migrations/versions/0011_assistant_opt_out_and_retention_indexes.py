"""assistant opt-out and the indexes the retention sweeps use

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-14 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("assistant_opt_out", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_provider_usage_events_created", "provider_usage_events", ["created_at"])
    op.create_index("ix_rate_limit_events_created", "rate_limit_events", ["created_at"])
    op.create_index("ix_chat_runs_status_finished", "chat_runs", ["status", "finished_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_runs_status_finished", table_name="chat_runs")
    op.drop_index("ix_rate_limit_events_created", table_name="rate_limit_events")
    op.drop_index("ix_provider_usage_events_created", table_name="provider_usage_events")
    op.drop_column("users", "assistant_opt_out")
