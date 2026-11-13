"""Runs one assistant turn and turns it into server-sent events.

This runs *after* the HTTP endpoint has returned (inside StreamingResponse), so it opens its
own database session rather than relying on the request's. The graph runs on a worker thread
so the response can keep sending keep-alive pings while a model call is in flight.

Whatever happens, the turn ends with one persisted assistant message and a run status:

  completed              the answer streamed fully
  awaiting_confirmation  the assistant proposed a change; the checkpoint waits for a decision
  failed                 a model error (capacity, outage...); the checkpoint is kept so
                         /resume can continue without repeating tool calls
  cancelled              the user pressed Stop or went away; whatever streamed is kept
"""

import logging
import queue
import threading
import uuid
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import AbstractContextManager, closing
from datetime import timedelta
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.assistant.actions import ActionStore
from app.assistant.context import ContextBuilder
from app.assistant.graph import AgentDeps, Cancelled, ChatState, build_graph
from app.assistant.prompts import PROMPT_VERSION, system_prompt
from app.assistant.sse import PING, sse
from app.assistant.tools import build_read_tools
from app.assistant.write_tools import build_write_tools
from app.core.clock import Clock
from app.core.config import Settings
from app.llm import build_llm_gateway
from app.llm.catalog import Provider
from app.llm.errors import LLMError
from app.llm.providers.base import ChatProvider
from app.models.chat import ChatMessage, ChatRun
from app.repositories.chat import ConversationRepository, MessageRepository, RunRepository
from app.repositories.chat_action import PendingActionRepository

logger = logging.getLogger("app.assistant")

SessionScope = Callable[[], AbstractContextManager[Session]]
RECURSION_LIMIT = 24
RESUMABLE_CODES = frozenset(
    {
        "assistant_capacity",
        "assistant_busy",
        "assistant_unavailable",
        "assistant_timeout",
        "internal_error",
    }
)
INTERNAL_ERROR = "Something went wrong on our side. Please try again."
MESSAGE_STATUS = {
    "completed": "complete",
    "awaiting_confirmation": "awaiting",
    "failed": "failed",
    "cancelled": "cancelled",
}


class TurnRunner:
    def __init__(
        self,
        *,
        session_scope: SessionScope,
        settings: Settings,
        clock: Clock,
        providers: Mapping[Provider, ChatProvider],
        checkpointer: BaseCheckpointSaver[str],
        user_id: int,
        first_name: str,
    ) -> None:
        self.session_scope = session_scope
        self.settings = settings
        self.clock = clock
        self.providers = providers
        self.checkpointer = checkpointer
        self.user_id = user_id
        self.first_name = first_name

    def stream(
        self, run_id: uuid.UUID, *, resume: bool = False, resume_value: object | None = None
    ) -> Iterator[str]:
        with self.session_scope() as session:
            yield from _Turn(self, session, run_id, resume, resume_value).run()


class _Turn:
    def __init__(
        self,
        owner: TurnRunner,
        session: Session,
        run_id: uuid.UUID,
        resume: bool,
        resume_value: object | None,
    ) -> None:
        self.owner = owner
        self.session = session
        self.run_id = run_id
        self.resume = resume or resume_value is not None
        self.resume_value = resume_value
        self.seq = 0
        self.streamed = ""
        self.tool_log: list[dict[str, Any]] = []
        self.changed: set[str] = set()
        self.local_cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.runs = RunRepository(session, owner.user_id)
        self.messages = MessageRepository(session, owner.user_id)
        self.conversations = ConversationRepository(session, owner.user_id)
        self.actions = PendingActionRepository(session, owner.user_id)

    def event(self, name: str, data: dict[str, Any]) -> str:
        self.seq += 1
        return sse(self.seq, name, data)

    # ---- the turn -------------------------------------------------------------------------

    def run(self) -> Iterator[str]:
        owner = self.owner
        settings = owner.settings
        run = self.runs.get_uuid(self.run_id)
        if run is None:
            yield self.event(
                "error",
                {
                    "code": "not_found",
                    "message": "That reply no longer exists.",
                    "recoverable": False,
                },
            )
            return
        conversation = self.conversations.get(run.conversation_id)
        user_message = self.messages.get(run.user_message_id)
        assert conversation is not None and user_message is not None
        gateway = build_llm_gateway(
            settings,
            self.session,
            owner.clock,
            user_id=owner.user_id,
            providers=dict(owner.providers),
        )
        yield self.event(
            "run_started",
            {
                "run_id": str(run.id),
                "conversation_id": conversation.id,
                "user_message_id": user_message.id,
                "resumed": self.resume,
            },
        )
        deps: AgentDeps | None = None
        try:
            context = ContextBuilder(self.messages, gateway).build(conversation, user_message.seq)
            self.session.commit()  # keeps a freshly folded summary even if the run fails
            deps = AgentDeps(
                gateway=gateway,
                tools=build_read_tools(
                    self.session,
                    owner.clock,
                    settings,
                    owner.user_id,
                    timeout_seconds=settings.chat_tool_timeout_seconds,
                ),
                write_tools=(
                    build_write_tools(self.session, owner.clock, settings, owner.user_id)
                    if settings.chat_writes_enabled
                    else {}
                ),
                actions=ActionStore(
                    self.session,
                    owner.clock,
                    user_id=owner.user_id,
                    conversation_id=conversation.id,
                    run_id=run.id,
                    ttl=timedelta(minutes=settings.chat_action_ttl_minutes),
                ),
                system_prompt=system_prompt(
                    today=owner.clock.today(),
                    first_name=owner.first_name,
                    summary=context.summary,
                    writes_enabled=settings.chat_writes_enabled,
                ),
                context=context,
                run_id=str(run.id),
                is_cancelled=lambda: (
                    self.local_cancel.is_set() or self.runs.cancel_requested(run.id)
                ),
            )
            graph = build_graph(deps).compile(checkpointer=owner.checkpointer)
            config: RunnableConfig = {
                "configurable": {"thread_id": str(run.id)},
                "recursion_limit": RECURSION_LIMIT,
            }
            inputs: ChatState | Command[Any] | None
            if self.resume_value is not None:
                inputs = Command(resume=self.resume_value)
            elif self.resume:
                inputs = None
            else:
                inputs = {
                    "messages": [HumanMessage(content=user_message.content)],
                    "tool_calls_made": 0,
                }
            with closing(self.pump(graph, inputs, config)) as items:
                for item in items:
                    if isinstance(item, str):
                        yield item  # a keep-alive ping
                    else:
                        yield from self.forward(item)
            state = graph.get_state(config).values
            # The graph's log covers every completed node of the run, including ones from
            # before a failure and resume (which this stream never saw).
            finished_log = [
                {k: entry.get(k) for k in ("name", "ok", "summary")}
                for entry in state.get("tool_log", [])
            ]
            pending = self.actions.pending_for_run(run.id)
            if pending is not None:
                message = self.finish(
                    run,
                    "awaiting_confirmation",
                    None,
                    tool_log=finished_log + self.tool_log,
                    model=state.get("model"),
                    switches=deps.budget.switches,
                )
                yield self.event(
                    "done",
                    {
                        "assistant_message_id": message.id,
                        "status": "awaiting_confirmation",
                        "action_id": str(pending.id),
                        "changed": sorted(self.changed),
                    },
                )
                return
            message = self.finish(
                run,
                "completed",
                None,
                tool_log=finished_log,
                model=state.get("model"),
                tokens=(state.get("prompt_tokens"), state.get("completion_tokens")),
                switches=deps.budget.switches,
            )
            logger.info(
                "assistant_turn",
                extra={
                    "run_id": str(run.id),
                    "outcome": "completed",
                    "model": state.get("model"),
                    "tools": len(finished_log),
                    "prompt_version": PROMPT_VERSION,
                },
            )
            yield self.event(
                "done",
                {
                    "assistant_message_id": message.id,
                    "status": "completed",
                    "model": state.get("model"),
                    "changed": sorted(self.changed),
                },
            )
        except Cancelled:
            message = self.finish(
                run, "cancelled", None, tool_log=self.tool_log, switches=_switches(deps)
            )
            yield self.event(
                "done",
                {
                    "assistant_message_id": message.id,
                    "status": "cancelled",
                    "changed": sorted(self.changed),
                },
            )
        except LLMError as exc:
            message = self.finish(
                run,
                "failed",
                exc.code,
                content=exc.user_message,
                tool_log=self.tool_log,
                switches=_switches(deps),
            )
            yield self.event(
                "error",
                {
                    "code": exc.code,
                    "message": exc.user_message,
                    "retry_after_seconds": exc.retry_after,
                    "recoverable": exc.code in RESUMABLE_CODES,
                },
            )
            yield self.event(
                "done",
                {
                    "assistant_message_id": message.id,
                    "status": "failed",
                    "changed": sorted(self.changed),
                },
            )
        except GeneratorExit:
            # The client went away mid-stream. Keep what was said; nothing more can be sent.
            # The pump's close() has already asked the worker to stop and waited for it.
            if self.worker is None or not self.worker.is_alive():
                self.finish(
                    run,
                    "cancelled",
                    "client_disconnected",
                    tool_log=self.tool_log,
                    switches=_switches(deps),
                )
            else:
                logger.error("assistant_worker_stuck", extra={"run_id": str(run.id)})
            raise
        except Exception:
            logger.exception("assistant_turn_failed", extra={"run_id": str(run.id)})
            self.session.rollback()
            message = self.finish(
                run,
                "failed",
                "internal_error",
                content=INTERNAL_ERROR,
                tool_log=self.tool_log,
                switches=_switches(deps),
            )
            yield self.event(
                "error", {"code": "internal_error", "message": INTERNAL_ERROR, "recoverable": True}
            )
            yield self.event(
                "done",
                {
                    "assistant_message_id": message.id,
                    "status": "failed",
                    "changed": sorted(self.changed),
                },
            )

    def pump(
        self,
        graph: CompiledStateGraph[ChatState, Any, Any, Any],
        inputs: ChatState | Command[Any] | None,
        config: RunnableConfig,
    ) -> Generator[dict[str, Any] | str, None, None]:
        """Graph events from a worker thread, with a ping whenever the graph is quiet.

        The session is only ever used by one thread at a time: the worker while the graph
        runs, this thread once the worker has finished (closing the iterator waits for it).
        """
        items: queue.Queue[object] = queue.Queue()
        done = object()

        def work() -> None:
            try:
                for item in graph.stream(inputs, config, stream_mode="custom"):
                    items.put(item)
            except BaseException as exc:  # handed to the main thread to raise
                items.put(exc)
                return
            items.put(done)

        self.worker = threading.Thread(target=work, name=f"chat-run-{self.run_id}", daemon=True)
        self.worker.start()
        try:
            while True:
                try:
                    item = items.get(timeout=self.owner.settings.chat_heartbeat_seconds)
                except queue.Empty:
                    yield PING
                    continue
                if item is done:
                    return
                if isinstance(item, BaseException):
                    raise item
                yield dict(item)  # type: ignore[call-overload]
        finally:
            if self.worker.is_alive():
                self.local_cancel.set()
                self.worker.join(timeout=self.owner.settings.llm_request_timeout_seconds + 5)

    def forward(self, item: dict[str, Any]) -> Iterator[str]:
        name = str(item.pop("event"))
        if name == "token":
            self.streamed += str(item.get("delta", ""))
        elif name == "tool_start" and self.streamed and not self.streamed.endswith("\n\n"):
            # Text the model wrote before looking something up becomes its own paragraph.
            self.streamed += "\n\n"
            yield self.event("token", {"delta": "\n\n"})
        elif name == "tool_end":
            self.tool_log.append({k: item.get(k) for k in ("name", "ok", "summary")})
            self.changed.update(str(c) for c in item.get("changed") or [])
        yield self.event(name, item)

    def finish(
        self,
        run: ChatRun,
        status: str,
        error_code: str | None,
        *,
        tool_log: list[dict[str, Any]],
        content: str | None = None,
        model: str | None = None,
        tokens: tuple[int | None, int | None] = (None, None),
        switches: int = 0,
    ) -> ChatMessage:
        now = self.owner.clock.now()
        message = self.messages.for_run(run.id)
        if message is None:
            message = self.messages.add(
                ChatMessage(
                    conversation_id=run.conversation_id,
                    seq=self.messages.next_seq(run.conversation_id),
                    role="assistant",
                    run_id=run.id,
                    created_at=now,
                )
            )
        # A reply continued after a confirmation keeps what it said before the card.
        prefix = message.content if message.status == "awaiting" else ""
        text = "\n\n".join(part for part in (prefix.strip(), self.streamed.strip()) if part)
        if status == "failed":
            # Keep any partial answer visible above the error.
            text = f"{text}\n\n{content}".strip() if text else (content or "")
        message.content = text or ("(stopped)" if status == "cancelled" else "")
        message.status = MESSAGE_STATUS[status]
        message.error_code = error_code
        message.model = model or message.model
        if tokens != (None, None):
            message.prompt_tokens, message.completion_tokens = tokens
        message.tool_calls = _dedupe(tool_log) or None
        run.status = status
        run.error_code = error_code
        run.model_switches += switches
        run.finished_at = now if status != "awaiting_confirmation" else None
        conversation = self.conversations.get(run.conversation_id)
        if conversation is not None:
            conversation.last_message_at = now
        self.session.commit()
        if status in ("completed", "cancelled"):
            self.forget_checkpoint(run.id)
        return message

    def forget_checkpoint(self, run_id: uuid.UUID) -> None:
        try:
            self.owner.checkpointer.delete_thread(str(run_id))
        except Exception:  # housekeeping only; never fail a finished turn over it
            logger.warning("assistant_checkpoint_cleanup_failed", extra={"run_id": str(run_id)})


def _switches(deps: AgentDeps | None) -> int:
    return deps.budget.switches if deps is not None else 0


def _dedupe(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A node that re-ran after a confirmation reports its lookups again; keep each once."""
    seen: set[tuple[object, ...]] = set()
    out: list[dict[str, Any]] = []
    for entry in log:
        key = (entry.get("name"), entry.get("ok"), entry.get("summary"))
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out
