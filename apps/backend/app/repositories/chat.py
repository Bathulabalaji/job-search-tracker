import uuid
from datetime import datetime

from sqlalchemy import func, select, update

from app.models.chat import ACTIVE_RUN_STATUSES, ChatConversation, ChatMessage, ChatRun
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[ChatConversation]):
    model = ChatConversation

    def list(self, *, status: str | None, limit: int, offset: int) -> list[ChatConversation]:
        stmt = select(ChatConversation).where(ChatConversation.user_id == self.user_id)
        if status is not None:
            stmt = stmt.where(ChatConversation.status == status)
        stmt = stmt.order_by(ChatConversation.last_message_at.desc(), ChatConversation.id.desc())
        return list(self.session.scalars(stmt.limit(limit).offset(offset)))

    def count(self) -> int:
        stmt = select(func.count()).where(ChatConversation.user_id == self.user_id)
        return int(self.session.scalar(stmt) or 0)


class MessageRepository(BaseRepository[ChatMessage]):
    model = ChatMessage

    def page(
        self, conversation_id: int, *, before_seq: int | None, limit: int
    ) -> list[ChatMessage]:
        """The newest `limit` messages (older than `before_seq`), returned oldest first."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == self.user_id)
            .where(ChatMessage.conversation_id == conversation_id)
        )
        if before_seq is not None:
            stmt = stmt.where(ChatMessage.seq < before_seq)
        rows = list(self.session.scalars(stmt.order_by(ChatMessage.seq.desc()).limit(limit)))
        return rows[::-1]

    def after(
        self, conversation_id: int, after_seq: int | None, *, before_seq: int
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == self.user_id)
            .where(ChatMessage.conversation_id == conversation_id)
            .where(ChatMessage.seq < before_seq)
        )
        if after_seq is not None:
            stmt = stmt.where(ChatMessage.seq > after_seq)
        return list(self.session.scalars(stmt.order_by(ChatMessage.seq)))

    def next_seq(self, conversation_id: int) -> int:
        stmt = (
            select(func.coalesce(func.max(ChatMessage.seq), 0))
            .where(ChatMessage.user_id == self.user_id)
            .where(ChatMessage.conversation_id == conversation_id)
        )
        return int(self.session.scalar(stmt) or 0) + 1

    def by_client_id(self, conversation_id: int, client_id: uuid.UUID) -> ChatMessage | None:
        return self.session.scalar(
            select(ChatMessage)
            .where(ChatMessage.user_id == self.user_id)
            .where(ChatMessage.conversation_id == conversation_id)
            .where(ChatMessage.client_message_id == client_id)
        )

    def for_run(self, run_id: uuid.UUID) -> ChatMessage | None:
        return self.session.scalar(
            select(ChatMessage)
            .where(ChatMessage.user_id == self.user_id)
            .where(ChatMessage.run_id == run_id)
            .where(ChatMessage.role == "assistant")
        )


class RunRepository(BaseRepository[ChatRun]):
    model = ChatRun

    def get_uuid(self, run_id: uuid.UUID) -> ChatRun | None:
        return self.session.scalar(
            select(ChatRun).where(ChatRun.id == run_id).where(ChatRun.user_id == self.user_id)
        )

    def active(self, conversation_id: int) -> ChatRun | None:
        return self.session.scalar(
            select(ChatRun)
            .where(ChatRun.user_id == self.user_id)
            .where(ChatRun.conversation_id == conversation_id)
            .where(ChatRun.status.in_(ACTIVE_RUN_STATUSES))
        )

    def latest(self, conversation_id: int) -> ChatRun | None:
        return self.session.scalar(
            select(ChatRun)
            .where(ChatRun.user_id == self.user_id)
            .where(ChatRun.conversation_id == conversation_id)
            .order_by(ChatRun.started_at.desc())
            .limit(1)
        )

    def ids_for(self, conversation_id: int) -> list[uuid.UUID]:
        stmt = (
            select(ChatRun.id)
            .where(ChatRun.user_id == self.user_id)
            .where(ChatRun.conversation_id == conversation_id)
        )
        return list(self.session.scalars(stmt))

    def cancel_requested(self, run_id: uuid.UUID) -> bool:
        stmt = (
            select(ChatRun.cancel_requested)
            .where(ChatRun.id == run_id)
            .where(ChatRun.user_id == self.user_id)
        )
        return bool(self.session.scalar(stmt))

    def request_cancel(self, run_id: uuid.UUID) -> None:
        self.session.execute(
            update(ChatRun)
            .where(ChatRun.id == run_id)
            .where(ChatRun.user_id == self.user_id)
            .values(cancel_requested=True)
        )

    def expire_stale(self, conversation_id: int, started_before: datetime, now: datetime) -> None:
        """Runs left 'running' by a crashed or restarted worker would block the conversation."""
        self.session.execute(
            update(ChatRun)
            .where(ChatRun.user_id == self.user_id)
            .where(ChatRun.conversation_id == conversation_id)
            .where(ChatRun.status == "running")
            .where(ChatRun.started_at < started_before)
            .values(status="failed", error_code="interrupted", finished_at=now)
        )
