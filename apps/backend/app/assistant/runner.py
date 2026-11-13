"""Runs one assistant turn and turns it into server-sent events.

This runs *after* the HTTP endpoint has returned (inside StreamingResponse), so it opens its
own database session rather than relying on the request's. Whatever happens, the turn ends
with exactly one persisted assistant message and a terminal run status:

  completed  the answer streamed fully
  failed     a model error (capacity, outage...); the checkpoint is kept so /resume can
             continue from the last completed step without repeating tool calls
  cancelled  the user pressed Stop or went away; whatever streamed is kept
"""

import logging
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from app.assistant.context import ContextBuilder
from app.assistant.graph import AgentDeps, Cancelled, ChatState, build_graph
from app.assistant.prompts import PROMPT_VERSION, system_prompt
from app.assistant.sse import sse
from app.assistant.tools import build_read_tools
from app.core.clock import Clock
from app.core.config import Settings
from app.llm import build_llm_gateway
from app.llm.catalog import Provider
from app.llm.errors import LLMError
from app.llm.providers.base import ChatProvider
from app.models.chat import ChatMessage, ChatRun
from app.repositories.chat import ConversationRepository, MessageRepository, RunRepository

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

    def stream(self, run_id: uuid.UUID, *, resume: bool = False) -> Iterator[str]:
        with self.session_scope() as session:
            yield from _Turn(self, session, run_id, resume).run()


class _Turn:
    def __init__(self, owner: TurnRunner, session: Session, run_id: uuid.UUID, resume: bool):
        self.owner = owner
        self.session = session
        self.run_id = run_id
        self.resume = resume
        self.seq = 0
        self.streamed = ""
        self.tool_log: list[dict[str, Any]] = []
        self.runs = RunRepository(session, owner.user_id)
        self.messages = MessageRepository(session, owner.user_id)
        self.conversations = ConversationRepository(session, owner.user_id)

    def event(self, name: str, data: dict[str, Any]) -> str:
        self.seq += 1
        return sse(self.seq, name, data)

    def run(self) -> Iterator[str]:
        owner = self.owner
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
            owner.settings,
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
                tools=build_read_tools(self.session, owner.clock, owner.settings, owner.user_id),
                system_prompt=system_prompt(
                    today=owner.clock.today(), first_name=owner.first_name, summary=context.summary
                ),
                context=context,
                run_id=str(run.id),
                is_cancelled=lambda: self.runs.cancel_requested(run.id),
            )
            graph = build_graph(deps).compile(checkpointer=owner.checkpointer)
            config: RunnableConfig = {
                "configurable": {"thread_id": str(run.id)},
                "recursion_limit": RECURSION_LIMIT,
            }
            inputs: ChatState | None = None
            if not self.resume:
                inputs = {
                    "messages": [HumanMessage(content=user_message.content)],
                    "tool_calls_made": 0,
                }
            for item in graph.stream(inputs, config, stream_mode="custom"):
                yield from self.forward(dict(item))
            state = graph.get_state(config).values
            # The graph's log covers every tool call of the run, including ones made before a
            # failure and resume (which this stream never saw).
            self.tool_log = [
                {k: entry.get(k) for k in ("name", "ok", "summary")}
                for entry in state.get("tool_log", [])
            ]
            message = self.finish(
                run,
                "completed",
                None,
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
                    "tools": len(self.tool_log),
                    "prompt_version": PROMPT_VERSION,
                },
            )
            yield self.event(
                "done",
                {
                    "assistant_message_id": message.id,
                    "status": "completed",
                    "model": state.get("model"),
                },
            )
        except Cancelled:
            message = self.finish(run, "cancelled", None, switches=_switches(deps))
            yield self.event("done", {"assistant_message_id": message.id, "status": "cancelled"})
        except LLMError as exc:
            message = self.finish(
                run, "failed", exc.code, content=exc.user_message, switches=_switches(deps)
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
            yield self.event("done", {"assistant_message_id": message.id, "status": "failed"})
        except GeneratorExit:
            # The client went away mid-stream. Keep what was said; nothing more can be sent.
            self.finish(run, "cancelled", "client_disconnected", switches=_switches(deps))
            raise
        except Exception:
            logger.exception("assistant_turn_failed", extra={"run_id": str(run.id)})
            self.session.rollback()
            message = self.finish(
                run, "failed", "internal_error", content=INTERNAL_ERROR, switches=_switches(deps)
            )
            yield self.event(
                "error", {"code": "internal_error", "message": INTERNAL_ERROR, "recoverable": True}
            )
            yield self.event("done", {"assistant_message_id": message.id, "status": "failed"})

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
        yield self.event(name, item)

    def finish(
        self,
        run: ChatRun,
        status: str,
        error_code: str | None,
        *,
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
        text = self.streamed.strip()
        if status == "failed":
            # Keep any partial answer visible above the error.
            text = f"{text}\n\n{content}".strip() if text else (content or "")
        message.content = text or ("(stopped)" if status == "cancelled" else "")
        message.status = "complete" if status == "completed" else status
        message.error_code = error_code
        message.model = model
        message.prompt_tokens, message.completion_tokens = tokens
        message.tool_calls = self.tool_log or None
        run.status = status
        run.error_code = error_code
        run.model_switches += switches
        run.finished_at = now
        conversation = self.conversations.get(run.conversation_id)
        if conversation is not None:
            conversation.last_message_at = now
        self.session.commit()
        if status != "failed":
            self.forget_checkpoint(run.id)
        return message

    def forget_checkpoint(self, run_id: uuid.UUID) -> None:
        try:
            self.owner.checkpointer.delete_thread(str(run_id))
        except Exception:  # housekeeping only; never fail a finished turn over it
            logger.warning("assistant_checkpoint_cleanup_failed", extra={"run_id": str(run_id)})


def _switches(deps: AgentDeps | None) -> int:
    return deps.budget.switches if deps is not None else 0
