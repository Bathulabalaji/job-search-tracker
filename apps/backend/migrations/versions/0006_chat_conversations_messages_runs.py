"""chat conversations, messages and runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_through_seq", sa.Integer(), nullable=True),
        sa.Column(
            "last_message_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversations")),
    )
    op.create_index(op.f("ix_chat_conversations_user_id"), "chat_conversations", ["user_id"])
    op.create_index(
        "ix_chat_conversations_user_last", "chat_conversations", ["user_id", "last_message_at"]
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="complete", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("client_message_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_chat_messages_conversation_id_chat_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(op.f("ix_chat_messages_user_id"), "chat_messages", ["user_id"])
    op.create_index(
        "uq_chat_messages_conversation_seq",
        "chat_messages",
        ["conversation_id", "seq"],
        unique=True,
    )
    op.create_index(
        "uq_chat_messages_client_id",
        "chat_messages",
        ["conversation_id", "client_message_id"],
        unique=True,
        postgresql_where=sa.text("client_message_id IS NOT NULL"),
    )

    op.create_table(
        "chat_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="running", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("model_switches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_chat_runs_conversation_id_chat_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            ["chat_messages.id"],
            name=op.f("fk_chat_runs_user_message_id_chat_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_chat_runs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_runs")),
    )
    op.create_index(op.f("ix_chat_runs_user_id"), "chat_runs", ["user_id"])
    op.create_index(
        "uq_chat_runs_one_active",
        "chat_runs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'awaiting_confirmation')"),
    )


def downgrade() -> None:
    op.drop_table("chat_runs")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
