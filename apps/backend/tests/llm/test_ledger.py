from collections.abc import Collection, Sequence
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.llm.catalog import Catalog, ModelSpec, Provider, load_catalog
from app.llm.ledger import CIRCUIT_CLOSED, CIRCUIT_HALF_OPEN, CIRCUIT_OPEN, BudgetLedger
from tests.llm.helpers import MovableClock

ALL = frozenset(Provider)
GROQ_70B = "openai/gpt-oss-120b"
GROQ_120B = "qwen/qwen3.8-27b"
GEMINI = "gemini-3.5-flash-lite"
GUARD = "meta-llama/llama-prompt-guard-2-86m"


def ledger(db: Session, clock: MovableClock, catalog: Catalog | None = None) -> BudgetLedger:
    return BudgetLedger(db, clock.clock, catalog or load_catalog(), circuit_failures=3)


def picked(
    budget: BudgetLedger,
    candidates: Sequence[str],
    est: int = 10,
    *,
    providers: Collection[Provider] = ALL,
    exclude: Collection[str] = (),
    need_tools: bool = False,
) -> str | None:
    pick = budget.pick(candidates, est, providers=providers, exclude=exclude, need_tools=need_tools)
    return pick.spec.name if pick.spec is not None else None


def state_of(budget: BudgetLedger, name: str):  # type: ignore[no-untyped-def]
    [state] = [s for s in budget.status() if s.resource == name]
    return state


def test_pick_reserves_a_request_and_the_estimated_tokens(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    assert picked(budget, (GROQ_70B,), 1200) == GROQ_70B
    state = state_of(budget, GROQ_70B)
    assert (state.minute_requests, state.minute_tokens) == (1, 1200)
    assert (state.day_requests, state.day_tokens) == (1, 1200)


def test_rpm_exhaustion_moves_to_the_next_candidate_and_reports_the_wait(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock, load_catalog(f'{{"{GROQ_70B}": {{"rpm": 1}}}}'))
    assert picked(budget, (GROQ_70B, GROQ_120B)) == GROQ_70B
    assert picked(budget, (GROQ_70B, GROQ_120B)) == GROQ_120B
    blocked = budget.pick((GROQ_70B,), 10, providers=ALL)
    assert blocked.spec is None
    assert blocked.retry_after == 60  # NOW is exactly on the minute
    clock.advance(seconds=61)
    assert picked(budget, (GROQ_70B,)) == GROQ_70B  # a new minute window


def test_tpm_counts_estimated_tokens_and_a_day_quota_waits_for_the_window(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock, load_catalog(f'{{"{GROQ_70B}": {{"tpm": 5000, "tpd": 6000}}}}'))
    assert picked(budget, (GROQ_70B,), 4000) == GROQ_70B
    assert picked(budget, (GROQ_70B,), 1500) is None  # 5500 > tpm
    clock.advance(minutes=1)
    assert picked(budget, (GROQ_70B,), 1500) == GROQ_70B  # 5500 <= tpd
    clock.advance(minutes=1)
    daily = budget.pick((GROQ_70B,), 1500, providers=ALL)
    assert daily.spec is None
    assert daily.retry_after is not None and daily.retry_after > 23 * 3600  # rolling 24h


def test_google_day_window_resets_at_midnight_pacific(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock, load_catalog(f'{{"{GEMINI}": {{"rpd": 1}}}}'))
    assert picked(budget, (GEMINI,)) == GEMINI
    blocked = budget.pick((GEMINI,), 10, providers=ALL)
    assert blocked.spec is None and blocked.retry_after is not None
    pacific = clock.now.astimezone(ZoneInfo("America/Los_Angeles"))
    midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    assert abs(blocked.retry_after - (midnight - clock.now).total_seconds()) <= 1
    clock.now = midnight + timedelta(seconds=1)
    assert picked(budget, (GEMINI,)) == GEMINI


def test_prompt_too_large_is_reported_separately_from_no_budget(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    pick = budget.pick((GROQ_70B, GROQ_120B), 20_000, providers=ALL)
    assert pick.spec is None and pick.skipped_for_size and pick.retry_after is None
    assert picked(budget, (GEMINI,), 20_000) == GEMINI  # a 24K prompt budget


def test_candidates_are_filtered_by_provider_and_capability(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    assert picked(budget, (GROQ_70B, GEMINI), providers={Provider.google}) == GEMINI
    assert picked(budget, (GUARD, GEMINI), need_tools=True) == GEMINI
    assert picked(budget, (GROQ_70B,), exclude={GROQ_70B}) is None


def test_settle_replaces_the_reservation_and_trusts_headers(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    spec = budget.pick((GROQ_70B,), 1000, providers=ALL).spec
    assert spec is not None
    budget.settle(
        spec,
        est_tokens=1000,
        prompt_tokens=700,
        completion_tokens=50,
        headers={
            "x-ratelimit-remaining-requests": "0",
            "x-ratelimit-reset-requests": "45s",
            "x-ratelimit-remaining-tokens": "9000",
            "x-ratelimit-reset-tokens": "5s",
        },
    )
    state = state_of(budget, GROQ_70B)
    assert state.minute_tokens == 750
    assert state.remaining_requests == 0 and not state.available
    blocked = budget.pick((GROQ_70B,), 10, providers=ALL)
    assert blocked.spec is None and blocked.retry_after == 45
    clock.advance(seconds=46)
    assert picked(budget, (GROQ_70B,)) == GROQ_70B


def test_rate_limited_cools_the_model_down_and_a_day_quota_until_the_reset(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    spec = budget.catalog.get(GROQ_70B)
    budget.mark_rate_limited(spec, kind="minute", retry_after=20)
    blocked = budget.pick((GROQ_70B,), 10, providers=ALL)
    assert blocked.spec is None and blocked.retry_after == 20
    clock.advance(seconds=21)
    assert picked(budget, (GROQ_70B,)) == GROQ_70B

    budget.mark_rate_limited(spec, kind="day", retry_after=None)
    blocked = budget.pick((GROQ_70B,), 10, providers=ALL)
    assert blocked.spec is None and blocked.retry_after is not None
    assert blocked.retry_after > 23 * 3600
    assert state_of(budget, GROQ_70B).reason == "day_quota"


def test_three_failures_open_the_circuit_and_one_success_closes_it(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    spec = budget.catalog.get(GROQ_70B)
    budget.mark_failure(spec)
    budget.mark_failure(spec)
    assert picked(budget, (GROQ_70B,)) == GROQ_70B
    budget.mark_failure(spec)
    blocked = budget.pick((GROQ_70B,), 10, providers=ALL)
    assert blocked.spec is None and blocked.retry_after == 60
    state = state_of(budget, GROQ_70B)
    assert state.circuit_state == CIRCUIT_OPEN and state.reason == "circuit_open"

    clock.advance(seconds=61)
    assert picked(budget, (GROQ_70B,)) == GROQ_70B  # half-open: one probe allowed
    assert state_of(budget, GROQ_70B).circuit_state == CIRCUIT_HALF_OPEN
    budget.mark_failure(spec)  # the probe failed: straight back to open
    assert picked(budget, (GROQ_70B,)) is None

    clock.advance(seconds=61)
    budget.settle(spec, est_tokens=10, prompt_tokens=10, completion_tokens=5)
    state = state_of(budget, GROQ_70B)
    assert state.circuit_state == CIRCUIT_CLOSED and state.available


def test_reset_cooldowns_and_usage_summary(db: Session) -> None:
    clock = MovableClock()
    budget = ledger(db, clock)
    spec = budget.catalog.get(GROQ_70B)
    budget.mark_rate_limited(spec, kind="minute", retry_after=600)
    assert budget.reset_cooldowns() == 1
    assert picked(budget, (GROQ_70B,)) == GROQ_70B

    budget.record(
        spec,
        task="chat.agent",
        outcome="ok",
        prompt_tokens=100,
        completion_tokens=20,
        latency_ms=400,
        user_id=db.info["user_id"],
    )
    budget.record(
        spec,
        task="chat.agent",
        outcome="ok",
        prompt_tokens=50,
        completion_tokens=10,
        latency_ms=200,
    )
    budget.record(spec, task="chat.agent", outcome="rate_limited", error_code="assistant_busy")
    rows = budget.usage(clock.now - timedelta(days=1))
    by_outcome = {row.outcome: row for row in rows}
    assert by_outcome["ok"].calls == 2
    assert by_outcome["ok"].prompt_tokens == 150
    assert by_outcome["ok"].avg_latency_ms == 300
    assert by_outcome["rate_limited"].calls == 1


def test_unknown_models_in_the_catalog_still_get_a_state_row(db: Session) -> None:
    clock = MovableClock()
    catalog = Catalog([ModelSpec(name="custom/model", provider=Provider.groq, rpm=2)])
    budget = ledger(db, clock, catalog)
    assert picked(budget, ("custom/model",)) == "custom/model"
    assert [s.resource for s in budget.status()] == ["custom/model"]
