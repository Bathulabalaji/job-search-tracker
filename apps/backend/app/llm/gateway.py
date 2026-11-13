"""Picks a model for a task, calls it, and falls back when it cannot answer.

The rules, in one place:
- a 429 cools that model down and the call moves to the next candidate;
- a 5xx or timeout is retried once on the same model, then the model is marked failed
  (enough failures open its circuit) and the call moves on;
- a prompt that no candidate can take is retried on the task's "large" variant;
- a run may switch models at most `max_switches` times and must finish before its deadline,
  so a bad hour degrades into one clear error instead of a storm of calls.

Completed work is never redone here: the gateway only re-issues the single LLM call that
failed. The agent (Phase 1) keeps tool results in its own state across these switches.
"""

import logging
import random
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import perf_counter

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from pydantic import BaseModel

from app.core.clock import Clock
from app.llm.catalog import Catalog, ModelKind, ModelSpec, Provider
from app.llm.errors import (
    AllModelsExhausted,
    AssistantDisabled,
    CapacityExceeded,
    ContentBlocked,
    ContextTooLong,
    EmbeddingUnavailable,
    LLMError,
    ProviderAuthFailed,
    ProviderBadRequest,
    ProviderUnavailable,
    RateLimited,
    RunTimedOut,
    StructuredOutputInvalid,
)
from app.llm.ledger import BudgetLedger
from app.llm.policy import LARGE_VARIANT, Policy, Task, large_prompt_threshold
from app.llm.providers.base import (
    ChatProvider,
    ChatReply,
    EmbedKind,
    ToolLike,
    Usage,
    message_content_text,
    usage_from_message,
)
from app.llm.tokens import estimate_json, estimate_messages, estimate_tokens

logger = logging.getLogger("app.llm")


@dataclass
class RunBudget:
    """How much fallback one piece of work may do. Shared across the calls of one agent run."""

    max_switches: int
    deadline: datetime
    switches: int = 0
    history: list[str] = field(default_factory=list)

    def switch(self, model: str, reason: str) -> None:
        self.switches += 1
        self.history.append(f"{model}:{reason}")
        if self.switches > self.max_switches:
            raise CapacityExceeded(
                f"gave up after {self.switches} model switches: {self.history}",
                model=model,
                retry_after=60,
            )


@dataclass
class ChatResult:
    task: Task
    model: str
    provider: str
    switches: int
    message: AIMessage | None = None
    parsed: BaseModel | None = None
    chunks: Iterator[AIMessageChunk] | None = None
    usage: Usage | None = None  # for streams, filled in once the stream has been consumed

    @property
    def text(self) -> str:
        return message_content_text(self.message) if self.message is not None else ""


def _tool_json(tool: ToolLike) -> object:
    if isinstance(tool, dict):
        return tool
    if isinstance(tool, type) and issubclass(tool, BaseModel):
        return tool.model_json_schema()
    return {"name": tool.name, "description": tool.description, "args": tool.args}


# Provider wording for "this model is gone for you" (Groq: model_not_found / does not exist;
# Google: "no longer available to new users"). Such a model is parked, not retried per call.
UNAVAILABLE_MARKERS = ("model_not_found", "does not exist", "no longer available")


def exc_outcome(exc: LLMError) -> str:
    """The `outcome` column of a usage event for a failed call."""
    if isinstance(exc, RateLimited):
        return "quota" if exc.kind == "day" else "rate_limited"
    if isinstance(exc, ProviderUnavailable):
        return "timeout" if exc.kind == "timeout" else "error"
    if isinstance(exc, ContentBlocked):
        return "blocked"
    if isinstance(exc, ProviderBadRequest | ContextTooLong | StructuredOutputInvalid):
        return "bad_request"
    return "error"


class LLMGateway:
    def __init__(
        self,
        *,
        ledger: BudgetLedger,
        providers: Mapping[Provider, ChatProvider],
        policy: Policy,
        catalog: Catalog,
        clock: Clock,
        request_timeout: float = 30.0,
        run_timeout: float = 90.0,
        max_switches: int = 3,
        embedding_model: str = "gemini-embedding-001",
        embedding_dims: int = 768,
        user_id: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.ledger = ledger
        self.providers = dict(providers)
        self.policy = policy
        self.catalog = catalog
        self.clock = clock
        self.request_timeout = request_timeout
        self.run_timeout = run_timeout
        self.max_switches = max_switches
        self.embedding_model = embedding_model
        self.embedding_dims = embedding_dims
        self.user_id = user_id
        self.sleep = sleep
        self.disabled_providers: set[Provider] = set()

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    def new_budget(self) -> RunBudget:
        return RunBudget(
            max_switches=self.max_switches,
            deadline=self.clock.now() + timedelta(seconds=self.run_timeout),
        )

    # ---- chat -----------------------------------------------------------------------------

    def chat(
        self,
        task: Task,
        messages: Sequence[BaseMessage],
        *,
        tools: Sequence[ToolLike] | None = None,
        schema: type[BaseModel] | None = None,
        stream: bool = False,
        budget: RunBudget | None = None,
        run_id: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if not self.enabled:
            raise AssistantDisabled()
        budget = budget or self.new_budget()
        est = estimate_messages(messages)
        if tools:
            est += sum(estimate_json(_tool_json(t)) for t in tools)
        if schema is not None:
            est += estimate_json(schema.model_json_schema())
        excluded: set[str] = set()
        retried_once: set[str] = set()
        current_task = task
        escalated = False  # using the large variant because of the prompt's size
        threshold = large_prompt_threshold(task, self.policy, self.catalog)
        if threshold is not None and est > threshold:
            current_task = LARGE_VARIANT[task]
            escalated = True
            logger.info("llm_large_prompt", extra={"task": task.value, "est_tokens": est})
        while True:
            self._check_deadline(budget)
            spec = self._pick(current_task, est, excluded, tools, schema, escalated)
            if spec is None:  # nothing fits: move to the large variant and pick again
                current_task = LARGE_VARIANT[current_task]
                escalated = True
                continue
            provider = self.providers[spec.provider]
            started = perf_counter()
            failure: LLMError | None = None
            reply: ChatReply | None = None
            first_chunk: AIMessageChunk | None = None
            try:
                reply = provider.chat(
                    spec,
                    messages,
                    tools=tools,
                    schema=schema,
                    stream=stream,
                    timeout=self.request_timeout,
                    max_tokens=max_tokens or spec.max_completion_tokens,
                    temperature=temperature,
                )
                if stream and reply.chunks is not None:
                    # Pull the first chunk here so connection-time failures still fall back.
                    first_chunk = next(reply.chunks, None)
            except LLMError as exc:
                failure = exc
            except Exception as exc:  # an adapter bug: treat as transient, but log loudly
                logger.exception("llm_adapter_error", extra={"model": spec.name})
                failure = ProviderUnavailable(
                    repr(exc), provider=spec.provider.value, model=spec.name
                )

            if failure is None and reply is not None:
                if stream:
                    result = ChatResult(
                        task=current_task,
                        model=spec.name,
                        provider=spec.provider.value,
                        switches=budget.switches,
                    )
                    result.chunks = self._stream(
                        result, spec, current_task, reply, first_chunk, est, started, run_id
                    )
                    return result
                usage = self._usage(reply, est)
                self.ledger.settle(
                    spec,
                    est_tokens=est,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    headers=reply.headers,
                )
                self._record(spec, current_task.value, "ok", started, usage=usage, run_id=run_id)
                return ChatResult(
                    task=current_task,
                    model=spec.name,
                    provider=spec.provider.value,
                    switches=budget.switches,
                    message=reply.message,
                    parsed=reply.parsed,
                    usage=usage,
                )

            assert failure is not None
            self._on_error(failure, spec)
            self._record(
                spec,
                current_task.value,
                exc_outcome(failure),
                started,
                error_code=failure.code,
                run_id=run_id,
            )
            # ---- what to do next -------------------------------------------------------
            if isinstance(failure, RateLimited):
                budget.switch(spec.name, f"rate_limited_{failure.kind}")
                excluded.add(spec.name)
            elif isinstance(failure, ContextTooLong):
                large = LARGE_VARIANT.get(current_task)
                if large is None:
                    raise failure
                budget.switch(spec.name, "context_too_long")
                excluded.add(spec.name)
                current_task = large
            elif isinstance(failure, ProviderUnavailable | StructuredOutputInvalid):
                if spec.name not in retried_once:
                    retried_once.add(spec.name)
                    self.sleep(random.uniform(0.5, 1.5))
                    continue  # same model, once more
                if isinstance(failure, ProviderUnavailable):
                    self.ledger.mark_failure(spec)
                budget.switch(spec.name, failure.code)
                excluded.add(spec.name)
            elif isinstance(failure, ProviderAuthFailed):
                logger.error("llm_provider_auth_failed", extra={"provider": spec.provider.value})
                self.disabled_providers.add(spec.provider)
                budget.switch(spec.name, "auth_failed")
            elif isinstance(failure, ProviderBadRequest | ContentBlocked):
                if any(m in failure.detail for m in UNAVAILABLE_MARKERS):
                    # Retired, or not on this account: stop asking until the day window rolls.
                    logger.error("llm_model_unavailable", extra={"model": spec.name})
                    self.ledger.mark_rate_limited(
                        spec, kind="day", retry_after=None, reason="model_unavailable"
                    )
                budget.switch(spec.name, failure.code)
                excluded.add(spec.name)
            else:  # AssistantDisabled, RunTimedOut: nothing to fall back to
                raise failure

    def _pick(
        self,
        task: Task,
        est: int,
        excluded: set[str],
        tools: Sequence[ToolLike] | None,
        schema: type[BaseModel] | None,
        escalated: bool,
    ) -> ModelSpec | None:
        """A model with budget, or None when the caller should retry on the large variant."""
        pick = self.ledger.pick(
            self.policy.get(task, ()),
            est,
            providers=self._available_providers(),
            exclude=excluded,
            need_tools=bool(tools),
            need_json_schema=schema is not None,
        )
        if pick.spec is not None:
            return pick.spec
        if pick.skipped_for_size:
            if task in LARGE_VARIANT:
                return None
            raise ContextTooLong(f"{est} prompt tokens fit no model for {task.value}")
        if escalated and pick.retry_after is None:
            # The prompt needs a large-context model and none is configured or usable.
            raise ContextTooLong(f"{est} prompt tokens need a large model; none for {task.value}")
        raise AllModelsExhausted(
            f"no model with budget for {task.value}", retry_after=pick.retry_after
        )

    @staticmethod
    def _usage(reply: ChatReply, est: int) -> Usage:
        usage = reply.usage
        if usage is None and reply.message is not None:
            usage = usage_from_message(reply.message)
        if usage is None:
            completion = (
                estimate_tokens(message_content_text(reply.message)) if reply.message else 0
            )
            usage = Usage(est, completion, estimated=True)
        return usage

    def _stream(
        self,
        result: ChatResult,
        spec: ModelSpec,
        task: Task,
        reply: ChatReply,
        first_chunk: AIMessageChunk | None,
        est: int,
        started: float,
        run_id: str | None,
    ) -> Iterator[AIMessageChunk]:
        usage: Usage | None = None
        produced = 0
        try:
            if first_chunk is not None:
                produced += len(message_content_text(first_chunk))
                usage = usage_from_message(first_chunk) or usage
                yield first_chunk
            for chunk in reply.chunks or ():
                produced += len(message_content_text(chunk))
                usage = usage_from_message(chunk) or usage
                yield chunk
        except LLMError as exc:
            # Mid-stream failures cannot fall back (text already went out): report and stop.
            self._on_error(exc, spec)
            self._record(
                spec, task.value, exc_outcome(exc), started, error_code=exc.code, run_id=run_id
            )
            raise
        except Exception as exc:
            logger.exception("llm_stream_error", extra={"model": spec.name})
            self._record(
                spec, task.value, "error", started, error_code="stream_error", run_id=run_id
            )
            raise ProviderUnavailable(
                repr(exc), provider=spec.provider.value, model=spec.name
            ) from exc
        if usage is None:
            usage = Usage(est, estimate_tokens(" " * produced), estimated=True)
        self.ledger.settle(
            spec,
            est_tokens=est,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            headers=reply.headers,
        )
        self._record(spec, task.value, "ok", started, usage=usage, run_id=run_id)
        result.usage = usage

    # ---- embeddings -----------------------------------------------------------------------

    def embed(self, texts: Sequence[str], *, kind: EmbedKind = "document") -> list[list[float]]:
        if not texts:
            return []
        if not self.enabled:
            raise AssistantDisabled()
        spec = self.catalog.get(self.embedding_model)
        if spec.kind != ModelKind.embedding:
            raise EmbeddingUnavailable(f"{spec.name} is not an embedding model")
        provider = self.providers.get(spec.provider)
        if provider is None or spec.provider in self.disabled_providers:
            raise EmbeddingUnavailable(f"no provider configured for {spec.name}")
        est = sum(estimate_tokens(text) for text in texts)
        pick = self.ledger.pick((spec.name,), est, providers={spec.provider})
        if pick.spec is None:
            raise EmbeddingUnavailable("embedding budget exhausted", retry_after=pick.retry_after)
        started = perf_counter()
        try:
            vectors = provider.embed(
                spec, texts, kind=kind, dims=self.embedding_dims, timeout=self.request_timeout
            )
        except LLMError as exc:
            self._on_error(exc, spec)
            if isinstance(exc, ProviderUnavailable):
                self.ledger.mark_failure(spec)
            self._record(
                spec, "embed", exc_outcome(exc), started, error_code=exc.code, kind="embedding"
            )
            raise EmbeddingUnavailable(
                exc.detail, model=spec.name, retry_after=exc.retry_after
            ) from exc
        usage = Usage(prompt_tokens=est, completion_tokens=0, estimated=True)
        self.ledger.settle(spec, est_tokens=est, prompt_tokens=est, completion_tokens=0)
        self._record(spec, "embed", "ok", started, usage=usage, kind="embedding")
        return vectors

    # ---- operator view --------------------------------------------------------------------

    def status(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for row in self.ledger.status():
            configured = Provider(row.provider) in self.providers
            reason = row.reason if configured else "no_api_key"
            rows.append(
                {
                    "model": row.resource,
                    "provider": row.provider,
                    "kind": row.kind,
                    "configured": configured,
                    "available": configured and row.available,
                    "reason": reason,
                    "minute": {"requests": row.minute_requests, "tokens": row.minute_tokens},
                    "day": {"requests": row.day_requests, "tokens": row.day_tokens},
                    "remaining": {
                        "requests": row.remaining_requests,
                        "tokens": row.remaining_tokens,
                    },
                    "cooldown_until": (
                        row.cooldown_until.isoformat() if row.cooldown_until else None
                    ),
                    "circuit": row.circuit_state,
                }
            )
        return rows

    # ---- internals ------------------------------------------------------------------------

    def _available_providers(self) -> set[Provider]:
        return set(self.providers) - self.disabled_providers

    def _check_deadline(self, budget: RunBudget) -> None:
        if self.clock.now() > budget.deadline:
            raise RunTimedOut(f"run exceeded {self.run_timeout}s with {budget.switches} switches")

    def _on_error(self, exc: LLMError, spec: ModelSpec) -> None:
        exc.provider = exc.provider or spec.provider.value
        exc.model = exc.model or spec.name
        if isinstance(exc, RateLimited):
            self.ledger.mark_rate_limited(
                spec, kind=exc.kind, retry_after=exc.retry_after, headers=exc.headers
            )
        logger.warning(
            "llm_call_failed",
            extra={
                "model": spec.name,
                "provider": spec.provider.value,
                "code": exc.code,
                "detail": exc.detail[:300],
            },
        )

    def _record(
        self,
        spec: ModelSpec,
        task: str,
        outcome: str,
        started: float,
        *,
        usage: Usage | None = None,
        error_code: str | None = None,
        run_id: str | None = None,
        kind: str = "llm",
    ) -> None:
        latency_ms = int((perf_counter() - started) * 1000)
        self.ledger.record(
            spec,
            task=task,
            outcome=outcome,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            error_code=error_code,
            user_id=self.user_id,
            run_id=run_id,
            kind=kind,
        )
        logger.info(
            "llm_call",
            extra={
                "task": task,
                "model": spec.name,
                "provider": spec.provider.value,
                "outcome": outcome,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "estimated": usage.estimated if usage else None,
                "latency_ms": latency_ms,
                "run_id": run_id,
            },
        )
