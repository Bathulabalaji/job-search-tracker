import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class ChatPendingAction(OwnedMixin, Base):
    """A change the assistant proposed. Nothing is written until the user confirms it here.

    Also the idempotency ledger for a run: the graph node that proposes actions re-runs after
    every confirmation, and finds the row instead of proposing (or executing) twice.
    """

    __tablename__ = "chat_pending_actions"
    __table_args__ = (
        Index("uq_chat_pending_actions_run_call", "run_id", "tool_call_id", unique=True),
        Index("ix_chat_pending_actions_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_runs.id", ondelete="CASCADE"))
    tool_call_id: Mapped[str] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    preview: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # pending | confirmed | rejected | expired | executed | failed
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String(500))
    warning: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
