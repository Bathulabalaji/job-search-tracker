"""Housekeeping queries that sweep across every user's rows by age.

Global on purpose, like the provider ledger: retention is a property of the deployment, not
of one user, so nothing here filters by user_id (see tests/unit/test_repository_scoping.py).
Every method is safe to run twice: it only touches rows that are still past their time.
"""

import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.auth import RateLimitEvent
from app.models.chat import ChatConversation, ChatRun
from app.models.chat_action import ChatPendingAction
from app.models.provider_ledger import ProviderUsageEvent

FINISHED = ("completed", "failed", "cancelled")


class MaintenanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def finished_run_ids(self, *, finished_before: datetime, since: datetime) -> list[uuid.UUID]:
        """Runs that ended in the window; deleting a thread that is already gone is a no-op."""
        stmt = select(ChatRun.id).where(
            ChatRun.status.in_(FINISHED),
            ChatRun.finished_at < finished_before,
            ChatRun.finished_at >= since,
        )
        return list(self.session.scalars(stmt))

    def expire_pending_actions(self, now: datetime) -> int:
        """Overdue confirmations expire, and the runs waiting on them are closed."""
        overdue = select(ChatPendingAction.run_id).where(
            ChatPendingAction.status == "pending", ChatPendingAction.expires_at <= now
        )
        self.session.execute(
            update(ChatRun)
            .where(ChatRun.status == "awaiting_confirmation", ChatRun.id.in_(overdue))
            .values(status="cancelled", error_code="action_expired", finished_at=now)
        )
        result = self.session.execute(
            update(ChatPendingAction)
            .where(ChatPendingAction.status == "pending", ChatPendingAction.expires_at <= now)
            .values(status="expired", decision_at=now)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def archive_idle_conversations(self, before: datetime) -> int:
        result = self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.status == "active", ChatConversation.last_message_at < before)
            .values(status="archived")
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def purge_idle_conversations(self, before: datetime) -> tuple[int, list[uuid.UUID]]:
        """Delete archived conversations idle since `before`; also returns their run ids so the
        caller can drop the checkpoints."""
        ids = list(
            self.session.scalars(
                select(ChatConversation.id).where(
                    ChatConversation.status == "archived", ChatConversation.last_message_at < before
                )
            )
        )
        if not ids:
            return 0, []
        run_ids = list(
            self.session.scalars(select(ChatRun.id).where(ChatRun.conversation_id.in_(ids)))
        )
        self.session.execute(delete(ChatConversation).where(ChatConversation.id.in_(ids)))
        return len(ids), run_ids

    def delete_usage_events(self, before: datetime) -> int:
        result = self.session.execute(
            delete(ProviderUsageEvent).where(ProviderUsageEvent.created_at < before)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def delete_rate_limit_events(self, before: datetime) -> int:
        result = self.session.execute(
            delete(RateLimitEvent).where(RateLimitEvent.created_at < before)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
