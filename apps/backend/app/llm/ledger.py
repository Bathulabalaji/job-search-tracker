"""Keeps every worker honest about how much of each model's free-tier budget is left.

One row per model in Postgres (like the auth rate limits), locked while a decision is made, so
two concurrent requests cannot both take the last slot. Counters roll per minute and per day;
what a provider reports in rate-limit headers overrides them while fresh; cooldowns and a
circuit breaker keep a struggling model out of rotation for a while.
"""

import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.llm.catalog import Catalog, ModelKind, ModelSpec, Provider
from app.llm.ratelimit_headers import RateLimitHeaders
from app.models.provider_ledger import ProviderResourceState, ProviderUsageEvent
from app.repositories.provider_ledger import ProviderLedgerRepository, UsageRow

logger = logging.getLogger("app.llm")

PACIFIC = ZoneInfo("America/Los_Angeles")  # Google's daily quotas reset at midnight Pacific
DAY = timedelta(days=1)

CIRCUIT_CLOSED = "closed"
CIRCUIT_OPEN = "open"
CIRCUIT_HALF_OPEN = "half_open"


@dataclass(frozen=True)
class Pick:
    spec: ModelSpec | None
    # Seconds until the earliest budget-blocked candidate frees up (None if none was blocked).
    retry_after: int | None
    # True when every otherwise usable candidate was skipped because the prompt is too big.
    skipped_for_size: bool


@dataclass(frozen=True)
class ResourceStatus:
    resource: str
    provider: str
    kind: str
    available: bool
    reason: str | None
    minute_requests: int
    minute_tokens: int
    day_requests: int
    day_tokens: int
    remaining_requests: int | None
    remaining_tokens: int | None
    cooldown_until: datetime | None
    circuit_state: str


class BudgetLedger:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        catalog: Catalog,
        *,
        circuit_failures: int = 3,
        circuit_cooldown_seconds: int = 60,
    ) -> None:
        self.session = session
        self.clock = clock
        self.catalog = catalog
        self.repo = ProviderLedgerRepository(session)
        self.circuit_failures = circuit_failures
        self.circuit_cooldown = timedelta(seconds=circuit_cooldown_seconds)

    # ---- choosing a model -----------------------------------------------------------------

    def pick(
        self,
        candidates: Sequence[str],
        est_tokens: int,
        *,
        providers: Collection[Provider],
        exclude: Collection[str] = (),
        need_tools: bool = False,
        need_json_schema: bool = False,
    ) -> Pick:
        """The first candidate that fits, with one request and `est_tokens` reserved on it."""
        waits: list[float] = []
        skipped_for_size = False
        considered = False
        for name in candidates:
            if name in exclude:
                continue
            spec = self.catalog.get(name)
            if spec.provider not in providers:
                continue
            if need_tools and not spec.supports_tools:
                continue
            if need_json_schema and not spec.supports_json_schema:
                continue
            if spec.kind != ModelKind.embedding and est_tokens > spec.max_prompt_tokens:
                skipped_for_size = True
                continue
            considered = True
            state = self.repo.lock(spec.name, spec.provider.value)
            now = self.clock.now()
            self._roll(state, spec, now)
            wait = self._blocked_for(state, spec, now, est_tokens)
            if wait is not None:
                waits.append(wait)
                self.session.commit()  # releases the row lock
                continue
            state.minute_requests += 1
            state.day_requests += 1
            state.minute_tokens += est_tokens
            state.day_tokens += est_tokens
            if state.reported_remaining_requests is not None:
                state.reported_remaining_requests -= 1
            if state.reported_remaining_tokens is not None:
                state.reported_remaining_tokens -= est_tokens
            self.session.commit()
            return Pick(spec, None, False)
        retry_after = max(1, ceil(min(waits))) if waits else None
        return Pick(None, retry_after, skipped_for_size and not considered)

    # ---- recording outcomes ---------------------------------------------------------------

    def settle(
        self,
        spec: ModelSpec,
        *,
        est_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Replace the reservation with what was actually used; a success also heals the circuit."""
        state = self.repo.lock(spec.name, spec.provider.value)
        now = self.clock.now()
        self._roll(state, spec, now)
        delta = prompt_tokens + completion_tokens - est_tokens
        state.minute_tokens = max(0, state.minute_tokens + delta)
        state.day_tokens = max(0, state.day_tokens + delta)
        self._apply_headers(state, headers, now)
        state.consecutive_failures = 0
        if state.circuit_state != CIRCUIT_CLOSED:
            logger.info("llm_circuit_closed", extra={"model": spec.name})
            state.circuit_state = CIRCUIT_CLOSED
        if state.cooldown_reason == "circuit_open":
            state.cooldown_until = None
            state.cooldown_reason = None
        self.session.commit()

    def mark_rate_limited(
        self,
        spec: ModelSpec,
        *,
        kind: str,
        retry_after: int | None,
        headers: Mapping[str, str] | None = None,
        reason: str | None = None,
    ) -> None:
        state = self.repo.lock(spec.name, spec.provider.value)
        now = self.clock.now()
        self._roll(state, spec, now)
        self._apply_headers(state, headers, now)
        if kind == "day":
            until = state.reported_requests_reset_at or self._day_reset_at(spec, state, now)
            why = reason or "day_quota"
        else:
            until = now + timedelta(seconds=retry_after or 60)
            why = reason or "rate_limited"
        if state.cooldown_until is None or until > state.cooldown_until:
            state.cooldown_until = until
            state.cooldown_reason = why
        logger.warning(
            "llm_rate_limited",
            extra={"model": spec.name, "kind": kind, "until": until.isoformat()},
        )
        self.session.commit()

    def mark_failure(self, spec: ModelSpec) -> None:
        """A transient failure. Enough of them in a row open the circuit for a cooldown."""
        state = self.repo.lock(spec.name, spec.provider.value)
        now = self.clock.now()
        self._roll(state, spec, now)
        state.consecutive_failures += 1
        state.last_failure_at = now
        tripped = state.consecutive_failures >= self.circuit_failures
        if state.circuit_state == CIRCUIT_HALF_OPEN or tripped:
            state.circuit_state = CIRCUIT_OPEN
            state.cooldown_until = now + self.circuit_cooldown
            state.cooldown_reason = "circuit_open"
            logger.warning(
                "llm_circuit_opened",
                extra={"model": spec.name, "failures": state.consecutive_failures},
            )
        self.session.commit()

    def record(
        self,
        spec: ModelSpec,
        *,
        task: str,
        outcome: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        error_code: str | None = None,
        user_id: int | None = None,
        run_id: str | None = None,
        kind: str = "llm",
    ) -> None:
        self.repo.add_event(
            ProviderUsageEvent(
                created_at=self.clock.now(),
                user_id=user_id,
                kind=kind,
                provider=spec.provider.value,
                resource=spec.name,
                task=task,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                outcome=outcome,
                error_code=error_code,
                run_id=run_id,
            )
        )
        self.session.commit()

    # ---- operator views -------------------------------------------------------------------

    def status(self) -> list[ResourceStatus]:
        rows: list[ResourceStatus] = []
        for spec in self.catalog.models():
            state = self.repo.lock(spec.name, spec.provider.value)
            now = self.clock.now()
            self._roll(state, spec, now)
            wait = self._blocked_for(state, spec, now, 0)
            self.session.commit()
            rows.append(
                ResourceStatus(
                    resource=spec.name,
                    provider=spec.provider.value,
                    kind=spec.kind.value,
                    available=wait is None,
                    reason=self._reason(state, spec, now) if wait is not None else None,
                    minute_requests=state.minute_requests,
                    minute_tokens=state.minute_tokens,
                    day_requests=state.day_requests,
                    day_tokens=state.day_tokens,
                    remaining_requests=state.reported_remaining_requests,
                    remaining_tokens=state.reported_remaining_tokens,
                    cooldown_until=state.cooldown_until,
                    circuit_state=state.circuit_state,
                )
            )
        return rows

    def reset_cooldowns(self) -> int:
        count = 0
        for state in self.repo.list_states():
            if state.cooldown_until is not None or state.circuit_state != CIRCUIT_CLOSED:
                count += 1
            state.cooldown_until = None
            state.cooldown_reason = None
            state.circuit_state = CIRCUIT_CLOSED
            state.consecutive_failures = 0
        self.session.commit()
        return count

    def usage(self, since: datetime) -> list[UsageRow]:
        return self.repo.usage_summary(since)

    # ---- internals ------------------------------------------------------------------------

    def _roll(self, state: ProviderResourceState, spec: ModelSpec, now: datetime) -> None:
        minute_start = now.replace(second=0, microsecond=0)
        if state.minute_window_start != minute_start:
            state.minute_window_start = minute_start
            state.minute_requests = 0
            state.minute_tokens = 0
        day_start = self._day_start(spec, state, now)
        if state.day_window_start != day_start:
            state.day_window_start = day_start
            state.day_requests = 0
            state.day_tokens = 0
        if state.reported_requests_reset_at is not None and now >= state.reported_requests_reset_at:
            state.reported_requests_reset_at = None
            state.reported_remaining_requests = None
        if state.reported_tokens_reset_at is not None and now >= state.reported_tokens_reset_at:
            state.reported_tokens_reset_at = None
            state.reported_remaining_tokens = None
        if state.cooldown_until is not None and now >= state.cooldown_until:
            if state.circuit_state == CIRCUIT_OPEN:
                state.circuit_state = CIRCUIT_HALF_OPEN  # let one probe through
            state.cooldown_until = None
            state.cooldown_reason = None

    @staticmethod
    def _day_start(spec: ModelSpec, state: ProviderResourceState, now: datetime) -> datetime:
        if spec.provider == Provider.google:
            local = now.astimezone(PACIFIC)
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
        # Groq documents daily limits without a fixed boundary: a 24-hour window from first use.
        if state.day_window_start is None or now - state.day_window_start >= DAY:
            return now
        return state.day_window_start

    def _day_reset_at(
        self, spec: ModelSpec, state: ProviderResourceState, now: datetime
    ) -> datetime:
        return self._day_start(spec, state, now) + DAY

    def _blocked_for(
        self, state: ProviderResourceState, spec: ModelSpec, now: datetime, est_tokens: int
    ) -> float | None:
        """Seconds until this model could take the call, or None if it can take it now."""
        if state.cooldown_until is not None and now < state.cooldown_until:
            return (state.cooldown_until - now).total_seconds()
        next_minute = 60 - now.second - now.microsecond / 1_000_000
        if spec.rpm and state.minute_requests + 1 > spec.rpm:
            return next_minute
        if spec.tpm and state.minute_tokens + est_tokens > spec.tpm:
            return next_minute
        day_reset = (self._day_reset_at(spec, state, now) - now).total_seconds()
        if spec.rpd and state.day_requests + 1 > spec.rpd:
            return day_reset
        if spec.tpd and state.day_tokens + est_tokens > spec.tpd:
            return day_reset
        if (
            state.reported_requests_reset_at is not None
            and state.reported_remaining_requests is not None
            and state.reported_remaining_requests < 1
        ):
            return (state.reported_requests_reset_at - now).total_seconds()
        if (
            state.reported_tokens_reset_at is not None
            and state.reported_remaining_tokens is not None
            and state.reported_remaining_tokens < max(est_tokens, 1)
        ):
            return (state.reported_tokens_reset_at - now).total_seconds()
        return None

    def _reason(self, state: ProviderResourceState, spec: ModelSpec, now: datetime) -> str:
        if state.cooldown_until is not None and now < state.cooldown_until:
            return state.cooldown_reason or "cooldown"
        if spec.rpm and state.minute_requests + 1 > spec.rpm:
            return "rpm"
        if spec.tpm and state.minute_tokens >= spec.tpm:
            return "tpm"
        if spec.rpd and state.day_requests + 1 > spec.rpd:
            return "rpd"
        if spec.tpd and state.day_tokens >= spec.tpd:
            return "tpd"
        return "reported_limit"

    @staticmethod
    def _apply_headers(
        state: ProviderResourceState, headers: Mapping[str, str] | None, now: datetime
    ) -> None:
        parsed = RateLimitHeaders.from_mapping(headers)
        if parsed.empty:
            return
        if parsed.remaining_requests is not None:
            state.reported_remaining_requests = parsed.remaining_requests
        if parsed.remaining_tokens is not None:
            state.reported_remaining_tokens = parsed.remaining_tokens
        if parsed.requests_reset_in is not None:
            state.reported_requests_reset_at = now + timedelta(seconds=parsed.requests_reset_in)
        if parsed.tokens_reset_in is not None:
            state.reported_tokens_reset_at = now + timedelta(seconds=parsed.tokens_reset_in)
