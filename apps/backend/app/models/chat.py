import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin

ACTIVE_RUN_STATUSES = ("running", "awaiting_confirmation")


class ChatConversation(OwnedMixin, Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (Index("ix_chat_conversations_user_last", "user_id", "last_message_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    # Rolling summary of messages up to and including `summary_through_seq`.
    summary: Mapped[str | None] = mapped_column(Text)
    summary_through_seq: Mapped[int | None]
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(OwnedMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("uq_chat_messages_conversation_seq", "conversation_id", "seq", unique=True),
        Index(
            "uq_chat_messages_client_id",
            "conversation_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )
    seq: Mapped[int]
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Tool activity of an assistant turn: [{name, args, ok, summary}]. Shown in the UI and
    # replayed into later prompts as one-line markers, never as raw tool output.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(16), default="complete", server_default="complete"
    )  # complete | failed | cancelled
    error_code: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatRun(OwnedMixin, Base):
    """One assistant turn. Its LangGraph checkpoints live under thread_id = str(id)."""

    __tablename__ = "chat_runs"
    __table_args__ = (
        Index(
            "uq_chat_runs_one_active",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('running', 'awaiting_confirmation')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )
    user_message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"))
    # running | completed | failed | cancelled (| awaiting_confirmation in Phase 1b)
    status: Mapped[str] = mapped_column(String(24), default="running", server_default="running")
    error_code: Mapped[str | None] = mapped_column(String(64))
    model_switches: Mapped[int] = mapped_column(default=0, server_default="0")
    cancel_requested: Mapped[bool] = mapped_column(default=False, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
