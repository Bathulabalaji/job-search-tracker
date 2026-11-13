"""Conversations, quotas and the bookkeeping around assistant turns.

Everything that can be refused is refused here, before any streaming starts, so the client
gets a normal HTTP error (409, 429, 503) instead of a stream that fails on its first event.
"""

import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant.runner import RESUMABLE_CODES
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ChatError, ChatQuotaError, NotFoundError, RateLimitedError
from app.llm.errors import AssistantDisabled
from app.models.chat import ChatConversation, ChatMessage, ChatRun
from app.repositories.chat import ConversationRepository, MessageRepository, RunRepository
from app.repositories.user import RateLimitRepository
from app.schemas.chat import (
    ChatConfig,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
    MessageRead,
    QuotaRead,
    RunRead,
    SendMessageRequest,
)
from app.services.rate_limit import RateLimiter

DAY = timedelta(days=1)
MINUTE = timedelta(minutes=1)
# A run still "running" after this long was orphaned by a crash or restart.
STALE_RUN_AFTER = timedelta(minutes=5)
TITLE_CHARS = 60
SUGGESTIONS = [
    "What's due today?",
    "Which applications have gone quiet for 2 weeks?",
    "How did this week go against my targets?",
    "Summarise my pipeline",
]


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_CHARS else line[: TITLE_CHARS - 1].rstrip() + "…"


class ChatService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, user_id: int) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.user_id = user_id
        self.conversations = ConversationRepository(session, user_id)
        self.messages = MessageRepository(session, user_id)
        self.runs = RunRepository(session, user_id)
        self.limiter = RateLimiter(session, clock)

    # ---- config ---------------------------------------------------------------------------

    def _day_bucket(self) -> str:
        return f"chat:day:{self.user_id}"

    def config(self) -> ChatConfig:
        used, _ = RateLimitRepository(self.session).window_stats(
            self._day_bucket(), self.clock.now() - DAY
        )
        return ChatConfig(
            enabled=self.settings.llm_enabled,
            messages_per_day=QuotaRead(limit=self.settings.chat_daily_messages, used=used),
            suggestions=SUGGESTIONS,
        )

    # ---- conversations --------------------------------------------------------------------

    def list_conversations(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[ChatConversation]:
        return self.conversations.list(status=status, limit=limit, offset=offset)

    def _get(self, conversation_id: int) -> ChatConversation:
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", conversation_id)
        return conversation

    def create(self, data: ConversationCreate) -> ChatConversation:
        if self.conversations.count() >= self.settings.chat_max_conversations:
            raise ChatError(
                "conversation_limit",
                f"You have {self.settings.chat_max_conversations} conversations. "
                "Delete an old one to start another.",
                409,
            )
        conversation = self.conversations.add(
            ChatConversation(
                title=_title(data.title) if data.title else "New chat",
                last_message_at=self.clock.now(),
            )
        )
        self.session.commit()
        return conversation

    def detail(
        self, conversation_id: int, *, before_seq: int | None, limit: int
    ) -> ConversationDetail:
        conversation = self._get(conversation_id)
        rows = self.messages.page(conversation.id, before_seq=before_seq, limit=limit)
        run = self.runs.latest(conversation.id)
        return ConversationDetail(
            conversation=ConversationRead.model_validate(conversation),
            messages=[MessageRead.model_validate(m) for m in rows],
            last_run=self._run_read(run) if run is not None else None,
        )

    def update(self, conversation_id: int, data: ConversationUpdate) -> ChatConversation:
        conversation = self._get(conversation_id)
        if data.title is not None:
            conversation.title = _title(data.title)
        if data.status is not None:
            conversation.status = data.status
        self.session.commit()
        return conversation

    def delete(self, conversation_id: int) -> list[uuid.UUID]:
        """Returns the run ids so the caller can drop their checkpoints too."""
        conversation = self._get(conversation_id)
        run_ids = self.runs.ids_for(conversation.id)
        self.conversations.delete(conversation)
        self.session.commit()
        return run_ids

    # ---- turns ----------------------------------------------------------------------------

    def start_turn(self, conversation_id: int, data: SendMessageRequest) -> uuid.UUID:
        if not self.settings.llm_enabled:
            raise AssistantDisabled()
        conversation = self._get(conversation_id)
        if self.messages.by_client_id(conversation.id, data.client_message_id) is not None:
            raise ChatError("duplicate_message", "That message was already sent.", 409)
        now = self.clock.now()
        self.runs.expire_stale(conversation.id, now - STALE_RUN_AFTER, now)
        if self.runs.active(conversation.id) is not None:
            raise ChatError(
                "run_in_progress", "I'm still answering your last message. Wait or press Stop.", 409
            )
        self._consume_quota()
        seq = self.messages.next_seq(conversation.id)
        message = self.messages.add(
            ChatMessage(
                conversation_id=conversation.id,
                seq=seq,
                role="user",
                content=data.content,
                client_message_id=data.client_message_id,
                created_at=now,
            )
        )
        if seq == 1 and conversation.title == "New chat":
            conversation.title = _title(data.content)
        conversation.last_message_at = now
        run = ChatRun(conversation_id=conversation.id, user_message_id=message.id, started_at=now)
        message.run_id = run.id = uuid.uuid4()
        self.runs.add(run)
        try:
            self.session.commit()
        except IntegrityError as exc:  # a concurrent request won the race for this conversation
            self.session.rollback()
            raise ChatError(
                "run_in_progress", "I'm still answering your last message.", 409
            ) from exc
        return run.id

    def prepare_resume(self, conversation_id: int, run_id: uuid.UUID) -> uuid.UUID:
        if not self.settings.llm_enabled:
            raise AssistantDisabled()
        conversation = self._get(conversation_id)
        run = self._get_run(conversation.id, run_id)
        if run.status != "failed" or run.error_code not in RESUMABLE_CODES:
            raise ChatError("not_resumable", "This reply can't be retried. Send it again.", 409)
        if self.runs.latest(conversation.id) is not run:
            raise ChatError("not_resumable", "Only the latest reply can be retried.", 409)
        self._consume_quota()
        run.status = "running"
        run.error_code = None
        run.cancel_requested = False
        run.finished_at = None
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ChatError("run_in_progress", "I'm still answering.", 409) from exc
        return run.id

    def cancel(self, conversation_id: int, run_id: uuid.UUID) -> None:
        run = self._get_run(self._get(conversation_id).id, run_id)
        if run.status == "running":
            self.runs.request_cancel(run.id)
            self.session.commit()

    def get_run(self, conversation_id: int, run_id: uuid.UUID) -> RunRead:
        return self._run_read(self._get_run(self._get(conversation_id).id, run_id))

    # ---- internals ------------------------------------------------------------------------

    def _get_run(self, conversation_id: int, run_id: uuid.UUID) -> ChatRun:
        run = self.runs.get_uuid(run_id)
        if run is None or run.conversation_id != conversation_id:
            raise ChatError("not_found", "That reply no longer exists.", 404)
        return run

    @staticmethod
    def _run_read(run: ChatRun) -> RunRead:
        read = RunRead.model_validate(run)
        read.resumable = run.status == "failed" and run.error_code in RESUMABLE_CODES
        return read

    def _consume_quota(self) -> None:
        try:
            self.limiter.consume(f"chat:min:{self.user_id}", self.settings.chat_per_minute, MINUTE)
        except RateLimitedError as exc:
            raise ChatQuotaError(
                exc.retry_after_seconds, "You're sending messages quickly. Wait a moment."
            ) from exc
        try:
            self.limiter.consume(self._day_bucket(), self.settings.chat_daily_messages, DAY)
        except RateLimitedError as exc:
            raise ChatQuotaError(
                exc.retry_after_seconds,
                f"You've used today's {self.settings.chat_daily_messages} assistant messages. "
                "They reset over the next day.",
            ) from exc
