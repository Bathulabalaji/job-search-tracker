"""Conversations, quotas and the bookkeeping around assistant turns.

Everything that can be refused is refused here, before any streaming starts, so the client
gets a normal HTTP error (409, 429, 503) instead of a stream that fails on its first event.
"""

import uuid
from datetime import timedelta

from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant.actions import action_payload
from app.assistant.runner import RESUMABLE_CODES
from app.assistant.write_tools import build_write_tools
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ChatError, ChatQuotaError, NotFoundError, RateLimitedError
from app.llm.errors import AssistantDisabled
from app.models.chat import ChatConversation, ChatMessage, ChatRun
from app.models.chat_action import ChatPendingAction
from app.repositories.chat import ConversationRepository, MessageRepository, RunRepository
from app.repositories.chat_action import PendingActionRepository
from app.repositories.user import RateLimitRepository
from app.schemas.chat import (
    ActionDecision,
    ActionRead,
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
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        user_id: int,
        checkpointer: BaseCheckpointSaver[str] | None = None,
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.user_id = user_id
        self.checkpointer = checkpointer
        self.conversations = ConversationRepository(session, user_id)
        self.messages = MessageRepository(session, user_id)
        self.runs = RunRepository(session, user_id)
        self.actions = PendingActionRepository(session, user_id)
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
        self._expire_overdue(conversation.id)
        rows = self.messages.page(conversation.id, before_seq=before_seq, limit=limit)
        run = self.runs.latest(conversation.id)
        pending = (
            self.actions.pending_for_run(run.id)
            if run is not None and run.status == "awaiting_confirmation"
            else None
        )
        return ConversationDetail(
            conversation=ConversationRead.model_validate(conversation),
            messages=[MessageRead.model_validate(m) for m in rows],
            last_run=self._run_read(run) if run is not None else None,
            pending_action=self._action_read(pending) if pending is not None else None,
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
        self._expire_overdue(conversation.id)
        active = self.runs.active(conversation.id)
        if active is not None and active.status == "awaiting_confirmation":
            raise ChatError("action_pending", "Confirm or decline the pending change first.", 409)
        if active is not None:
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
        elif run.status == "awaiting_confirmation":
            # Stop while a card is up: the change is declined and the reply ends here.
            pending = self.actions.pending_for_run(run.id)
            if pending is not None:
                self.actions.decide(pending.id, "rejected", self.clock.now())
            self._end_waiting_run(run, "cancelled", "cancelled", "(stopped)")

    # ---- actions (Phase 1b) -----------------------------------------------------------------

    def get_action(self, conversation_id: int, action_id: uuid.UUID) -> ActionRead:
        conversation = self._get(conversation_id)
        self._expire_overdue(conversation.id)
        return self._action_read(self._get_action(conversation.id, action_id))

    def decide(self, conversation_id: int, action_id: uuid.UUID, data: ActionDecision) -> uuid.UUID:
        """Record the user's decision and hand the run back to the graph. Returns the run id."""
        if not self.settings.llm_enabled:
            raise AssistantDisabled()
        conversation = self._get(conversation_id)
        action = self._get_action(conversation.id, action_id)
        now = self.clock.now()
        if action.status == "pending" and action.expires_at <= now:
            self._expire(action)
            raise ChatError(
                "action_expired", "That change expired before it was confirmed. Ask again.", 410
            )
        if action.status != "pending":
            raise ChatError("action_already_decided", "This change was already decided.", 409)
        run = self.runs.get_uuid(action.run_id)
        if run is None or run.status != "awaiting_confirmation":
            raise ChatError("not_resumable", "This reply is no longer waiting for a decision.", 409)
        if data.decision == "confirm" and data.edits:
            action.args = self._merge_edits(action, data.edits)
        decided = self.actions.decide(
            action.id, "confirmed" if data.decision == "confirm" else "rejected", now
        )
        if not decided:
            self.session.rollback()
            raise ChatError("action_already_decided", "This change was already decided.", 409)
        run.status = "running"
        run.cancel_requested = False
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ChatError("run_in_progress", "I'm still answering.", 409) from exc
        return run.id

    def _merge_edits(
        self, action: ChatPendingAction, edits: dict[str, object]
    ) -> dict[str, object]:
        editable = {
            str(f.get("name")) for f in action.preview.get("fields", []) if f.get("editable")
        }
        unknown = sorted(set(edits) - editable)
        if unknown:
            raise ChatError(
                "invalid_edits", f"These fields can't be edited: {', '.join(unknown)}", 422
            )
        tool = build_write_tools(self.session, self.clock, self.settings, self.user_id).get(
            action.tool_name
        )
        if tool is None:
            raise ChatError("invalid_edits", "This change can no longer be edited.", 422)
        merged = {**action.args, **{k: (v if v != "" else None) for k, v in edits.items()}}
        try:
            parsed = tool.args.model_validate(merged)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3]
            )
            raise ChatError("invalid_edits", problems, 422) from exc
        return parsed.model_dump(mode="json")

    def _get_action(self, conversation_id: int, action_id: uuid.UUID) -> ChatPendingAction:
        action = self.actions.get_uuid(action_id)
        if action is None or action.conversation_id != conversation_id:
            raise ChatError("not_found", "That change no longer exists.", 404)
        return action

    def _action_read(self, action: ChatPendingAction) -> ActionRead:
        return ActionRead.model_validate(action_payload(action))

    def _expire_overdue(self, conversation_id: int) -> None:
        run = self.runs.active(conversation_id)
        if run is None or run.status != "awaiting_confirmation":
            return
        pending = self.actions.pending_for_run(run.id)
        if pending is not None and pending.expires_at <= self.clock.now():
            self._expire(pending)

    def _expire(self, action: ChatPendingAction) -> None:
        action.status = "expired"
        action.decision_at = self.clock.now()
        run = self.runs.get_uuid(action.run_id)
        if run is not None and run.status == "awaiting_confirmation":
            self._end_waiting_run(
                run,
                "cancelled",
                "action_expired",
                "(This change expired before it was confirmed.)",
            )
        else:
            self.session.commit()

    def _end_waiting_run(self, run: ChatRun, status: str, code: str, note: str) -> None:
        now = self.clock.now()
        run.status = status
        run.error_code = code
        run.finished_at = now
        message = self.messages.for_run(run.id)
        if message is not None:
            message.status = status
            message.error_code = code
            message.content = f"{message.content}\n\n{note}".strip()
        self.session.commit()
        if self.checkpointer is not None:
            try:
                self.checkpointer.delete_thread(str(run.id))
            except Exception:  # housekeeping only
                pass

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
