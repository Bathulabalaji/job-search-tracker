import uuid
from datetime import datetime

from sqlalchemy import select, update

from app.models.chat_action import ChatPendingAction
from app.repositories.base import BaseRepository


class PendingActionRepository(BaseRepository[ChatPendingAction]):
    model = ChatPendingAction

    def get_uuid(self, action_id: uuid.UUID) -> ChatPendingAction | None:
        return self.session.scalar(
            select(ChatPendingAction)
            .where(ChatPendingAction.id == action_id)
            .where(ChatPendingAction.user_id == self.user_id)
        )

    def by_call(self, run_id: uuid.UUID, tool_call_id: str) -> ChatPendingAction | None:
        return self.session.scalar(
            select(ChatPendingAction)
            .where(ChatPendingAction.user_id == self.user_id)
            .where(ChatPendingAction.run_id == run_id)
            .where(ChatPendingAction.tool_call_id == tool_call_id)
        )

    def pending_for_run(self, run_id: uuid.UUID) -> ChatPendingAction | None:
        return self.session.scalar(
            select(ChatPendingAction)
            .where(ChatPendingAction.user_id == self.user_id)
            .where(ChatPendingAction.run_id == run_id)
            .where(ChatPendingAction.status == "pending")
            .order_by(ChatPendingAction.created_at)
            .limit(1)
        )

    def decide(self, action_id: uuid.UUID, status: str, now: datetime) -> bool:
        """Move a pending action to `status`. Atomic: of two concurrent decisions, one wins."""
        result = self.session.execute(
            update(ChatPendingAction)
            .where(ChatPendingAction.id == action_id)
            .where(ChatPendingAction.user_id == self.user_id)
            .where(ChatPendingAction.status == "pending")
            .where(ChatPendingAction.expires_at > now)
            .values(status=status, decision_at=now)
            .returning(ChatPendingAction.id)
        )
        return result.first() is not None
