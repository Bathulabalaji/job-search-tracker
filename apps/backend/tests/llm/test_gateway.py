from datetime import timedelta

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.errors import (
    AllModelsExhausted,
    AssistantDisabled,
    CapacityExceeded,
    ContentBlocked,
    ContextTooLong,
    EmbeddingUnavailable,
    ProviderAuthFailed,
    ProviderBadRequest,
    ProviderUnavailable,
    RateLimited,
    RunTimedOut,
    StructuredOutputInvalid,
)
from app.llm.policy import Task
from app.llm.providers.fake import FakeProvider, FakeStep
from app.models.provider_ledger import ProviderUsageEvent
from tests.llm.helpers import MovableClock, build_gateway, prompt

GROQ_70B = "openai/gpt-oss-120b"
GROQ_120B = "qwen/qwen3.8-27b"
GEMINI_LITE = "gemini-3.5-flash-lite"
GEMINI_FLASH = "gemini-3.8-flash"
GUARD = "meta-llama/llama-prompt-guard-2-86m"


def events(db: Session) -> list[ProviderUsageEvent]:
    return list(db.scalars(select(ProviderUsageEvent).order_by(ProviderUsageEvent.id)))


def reply(text: str, prompt_tokens: int | None = None, completion_tokens: int = 0) -> AIMessage:
    """A scripted answer, with reported usage when `prompt_tokens` is given."""
    if prompt_tokens is None:
        return AIMessage(content=text)
    return AIMessage(
        content=text,
        usage_metadata={
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


def availability(gateway_status: list[dict[str, object]], model: str) -> dict[str, object]:
    return {str(row["model"]): row for row in gateway_status}[model]


class Verdict(BaseModel):
    in_scope: bool
    intent: str


def test_a_plain_call_uses_the_first_candidate_and_records_usage(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [reply("Two follow-ups are due.", 40, 6)])
    gateway = build_gateway(db, clock, groq=groq, google=FakeProvider("google"))

    result = gateway.chat(Task.chat_agent, prompt())

    assert (result.model, result.provider, result.switches) == (GROQ_70B, "groq", 0)
    assert result.text == "Two follow-ups are due."
    assert result.usage is not None
    assert (result.usage.prompt_tokens, result.usage.estimated) == (40, False)
    [event] = events(db)
    assert (event.outcome, event.resource, event.task) == ("ok", GROQ_70B, "chat.agent")
    assert event.user_id == db.info["user_id"]
    assert (event.prompt_tokens, event.completion_tokens) == (40, 6)


def test_a_429_switches_models_and_cools_the_first_one_down(db: Session) -> None:
    clock = MovableClock()
    busy = RateLimited("tpm", kind="minute", retry_after=12)
    groq = FakeProvider("groq", [busy, reply("from 120b")])
    gateway = build_gateway(db, clock, groq=groq, google=FakeProvider("google"))

    result = gateway.chat(Task.chat_agent, prompt())

    assert (result.model, result.switches) == (GROQ_120B, 1)
    assert [c.model for c in groq.calls] == [GROQ_70B, GROQ_120B]
    assert groq.calls[0].messages == groq.calls[1].messages  # the same prompt, just elsewhere
    outcomes = [(e.resource, e.outcome) for e in events(db)]
    assert outcomes == [(GROQ_70B, "rate_limited"), (GROQ_120B, "ok")]
    state = availability(gateway.status(), GROQ_70B)
    assert state["available"] is False and state["reason"] == "rate_limited"
    clock.advance(seconds=13)
    assert availability(gateway.status(), GROQ_70B)["available"] is True


def test_a_day_quota_is_recorded_as_quota_and_blocks_until_tomorrow(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [RateLimited("rpd reached", kind="day"), reply("ok")])
    gateway = build_gateway(db, clock, groq=groq)
    gateway.chat(Task.chat_agent, prompt())
    assert events(db)[0].outcome == "quota"
    clock.advance(hours=1)
    assert availability(gateway.status(), GROQ_70B)["reason"] == "day_quota"


def test_a_server_error_is_retried_once_then_the_model_is_skipped(db: Session) -> None:
    clock = MovableClock()
    down = ProviderUnavailable("502")
    groq = FakeProvider("groq", [down, down, reply("ok")])
    gateway = build_gateway(db, clock, groq=groq)

    result = gateway.chat(Task.chat_agent, prompt())

    assert [c.model for c in groq.calls] == [GROQ_70B, GROQ_70B, GROQ_120B]
    assert (result.model, result.switches) == (GROQ_120B, 1)
    assert availability(gateway.status(), GROQ_70B)["circuit"] == "closed"  # one is not enough


def test_repeated_failures_open_the_circuit_so_the_model_is_not_even_tried(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq")
    gateway = build_gateway(db, clock, groq=groq)
    for _ in range(3):
        groq.script(ProviderUnavailable("boom"), ProviderUnavailable("boom"), reply("ok"))
        gateway.chat(Task.chat_agent, prompt())
    assert availability(gateway.status(), GROQ_70B)["circuit"] == "open"
    groq.calls.clear()
    groq.script(reply("ok"))
    result = gateway.chat(Task.chat_agent, prompt())
    assert result.model == GROQ_120B and [c.model for c in groq.calls] == [GROQ_120B]


def test_too_many_switches_end_in_a_capacity_error_with_history(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [RateLimited("a"), RateLimited("b")])
    google = FakeProvider("google", [RateLimited("c"), RateLimited("d")])
    gateway = build_gateway(db, clock, groq=groq, google=google, max_switches=3)
    with pytest.raises(CapacityExceeded) as info:
        gateway.chat(Task.chat_agent, prompt())
    assert info.value.retry_after == 60
    assert "capacity" in info.value.user_message.lower()
    assert info.value.detail.count("rate_limited") == 4  # four switches recorded


def test_when_no_model_has_budget_the_error_says_when_to_retry(db: Session) -> None:
    clock = MovableClock()
    limits = f'{{"{GROQ_70B}": {{"rpm": 1}}, "{GROQ_120B}": {{"rpm": 1}}}}'
    policy = f'{{"chat.agent": ["{GROQ_70B}", "{GROQ_120B}"]}}'
    gateway = build_gateway(
        db, clock, groq=FakeProvider("groq"), limits=limits, policy_override=policy
    )
    gateway.chat(Task.chat_agent, prompt())
    gateway.chat(Task.chat_agent, prompt())
    with pytest.raises(AllModelsExhausted) as info:
        gateway.chat(Task.chat_agent, prompt())
    assert info.value.retry_after == 60
    assert info.value.status_code == 429
    assert "about a minute" in info.value.user_message


def test_a_prompt_too_big_for_groq_goes_straight_to_the_large_variant(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq")
    google = FakeProvider("google", [reply("long answer")])
    gateway = build_gateway(db, clock, groq=groq, google=google)

    result = gateway.chat(Task.chat_agent, [HumanMessage(content="x" * 30_000)])

    assert groq.calls == []
    assert result.task is Task.chat_agent_large and result.model == GEMINI_FLASH
    assert result.switches == 0  # routing by size is not a failure


def test_a_context_error_from_the_provider_escalates_then_gives_up(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [ContextTooLong("too long")])
    google = FakeProvider("google", [reply("fits here")])
    gateway = build_gateway(db, clock, groq=groq, google=google)
    assert gateway.chat(Task.chat_agent, prompt()).model == GEMINI_FLASH

    google.script(ContextTooLong("still too long"))
    with pytest.raises(ContextTooLong) as info:
        gateway.chat(Task.chat_agent_large, prompt())
    assert info.value.status_code == 400
    assert "Start a new chat" in info.value.user_message


def test_a_prompt_nobody_can_take_is_a_context_error(db: Session) -> None:
    clock = MovableClock()
    gateway = build_gateway(db, clock, groq=FakeProvider("groq"))  # no Google: no large models
    with pytest.raises(ContextTooLong):
        gateway.chat(Task.chat_agent, [HumanMessage(content="x" * 30_000)])


def test_an_auth_failure_disables_that_provider_for_the_rest_of_the_run(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [ProviderAuthFailed("bad key")])
    google = FakeProvider("google", [reply("hi"), reply("again")])
    gateway = build_gateway(db, clock, groq=groq, google=google)
    assert gateway.chat(Task.chat_agent, prompt()).model == GEMINI_LITE
    assert gateway.chat(Task.chat_agent, prompt()).model == GEMINI_LITE
    assert len(groq.calls) == 1


@pytest.mark.parametrize("error", [ProviderBadRequest("schema"), ContentBlocked("safety")])
def test_bad_requests_and_blocked_content_move_on_without_a_retry(
    db: Session, error: Exception
) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [error, reply("ok")])
    gateway = build_gateway(db, clock, groq=groq)
    result = gateway.chat(Task.chat_agent, prompt())
    assert [c.model for c in groq.calls] == [GROQ_70B, GROQ_120B]
    assert result.switches == 1


def test_structured_output_is_parsed_and_invalid_json_is_retried_once(db: Session) -> None:
    clock = MovableClock()
    verdict = Verdict(in_scope=False, intent="smalltalk")
    good = FakeStep(message=reply("{}"), parsed=verdict)
    google = FakeProvider("google", [StructuredOutputInvalid("junk"), good])
    gateway = build_gateway(db, clock, google=google)

    result = gateway.chat(Task.extract_structured, prompt(), schema=Verdict)

    assert result.parsed == verdict
    assert [c.model for c in google.calls] == [GEMINI_LITE, GEMINI_LITE]
    assert all(c.schema is Verdict for c in google.calls)


def test_tools_are_passed_through_and_models_without_tool_support_are_skipped(
    db: Session,
) -> None:
    clock = MovableClock()
    call = AIMessage(content="", tool_calls=[{"name": "get_today", "args": {}, "id": "1"}])
    groq = FakeProvider("groq", [call])
    policy = f'{{"chat.agent": ["{GUARD}", "{GROQ_70B}"]}}'
    gateway = build_gateway(db, clock, groq=groq, policy_override=policy)

    class GetToday(BaseModel):
        """What is due today."""

    result = gateway.chat(Task.chat_agent, prompt(), tools=[GetToday])
    assert result.model == GROQ_70B
    assert groq.calls[0].tools == [GetToday]
    assert result.message is not None and result.message.tool_calls[0]["name"] == "get_today"


def test_streaming_yields_chunks_then_settles_usage(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [reply("one two three", 30, 3)])
    gateway = build_gateway(db, clock, groq=groq)

    result = gateway.chat(Task.chat_agent, prompt(), stream=True)

    assert result.chunks is not None and result.usage is None
    text = "".join(str(chunk.content) for chunk in result.chunks)
    assert text == "one two three"
    assert result.usage is not None and result.usage.prompt_tokens == 30
    [event] = events(db)
    assert (event.outcome, event.prompt_tokens, event.completion_tokens) == ("ok", 30, 3)


def test_a_stream_that_fails_to_connect_falls_back_like_any_other_call(db: Session) -> None:
    clock = MovableClock()
    groq = FakeProvider("groq", [RateLimited("busy"), reply("streamed")])
    gateway = build_gateway(db, clock, groq=groq)
    result = gateway.chat(Task.chat_agent, prompt(), stream=True)
    assert result.model == GROQ_120B
    assert "".join(str(c.content) for c in result.chunks or ()) == "streamed"


def test_the_run_deadline_is_enforced_before_each_attempt(db: Session) -> None:
    clock = MovableClock()
    gateway = build_gateway(db, clock, groq=FakeProvider("groq"), run_timeout=10)
    budget = gateway.new_budget()
    clock.advance(seconds=11)
    with pytest.raises(RunTimedOut):
        gateway.chat(Task.chat_agent, prompt(), budget=budget)


def test_with_no_provider_keys_everything_is_disabled(db: Session) -> None:
    clock = MovableClock()
    gateway = build_gateway(db, clock)
    assert not gateway.enabled
    with pytest.raises(AssistantDisabled):
        gateway.chat(Task.chat_agent, prompt())
    with pytest.raises(AssistantDisabled):
        gateway.embed(["x"])
    assert all(row["reason"] == "no_api_key" for row in gateway.status())


def test_embeddings_have_the_requested_size_and_no_fallback(db: Session) -> None:
    clock = MovableClock()
    google = FakeProvider("google")
    gateway = build_gateway(db, clock, google=google)

    vectors = gateway.embed(["python fastapi", "react typescript"], kind="document")

    assert len(vectors) == 2 and all(len(v) == 768 for v in vectors)
    assert google.embed_calls == [["python fastapi", "react typescript"]]
    [event] = events(db)
    assert (event.kind, event.task, event.outcome) == ("embedding", "embed", "ok")

    google.embed_error = RateLimited("quota", kind="minute", retry_after=25)
    with pytest.raises(EmbeddingUnavailable) as info:
        gateway.embed(["more"])
    assert info.value.retry_after == 25
    assert "Indexing is paused" in info.value.user_message
    with pytest.raises(EmbeddingUnavailable):  # now blocked by the cooldown, before any call
        gateway.embed(["more"])
    assert len(google.embed_calls) == 2


def test_embeddings_need_the_google_provider(db: Session) -> None:
    clock = MovableClock()
    gateway = build_gateway(db, clock, groq=FakeProvider("groq"))
    with pytest.raises(EmbeddingUnavailable, match="no provider"):
        gateway.embed(["x"])


def test_usage_events_survive_the_callers_rollback(db: Session) -> None:
    """The ledger commits on its own, so a failed request still leaves its usage behind."""
    clock = MovableClock()
    gateway = build_gateway(db, clock, groq=FakeProvider("groq"))
    gateway.chat(Task.chat_agent, prompt())
    db.rollback()  # what FastAPI's session teardown does after an exception
    assert len(events(db)) == 1
    assert gateway.ledger.status()[0].day_requests == 1
    clock.advance(seconds=1)
    assert clock.now > clock.now - timedelta(seconds=1)


def test_a_model_the_provider_does_not_know_is_parked_not_retried_every_call(db: Session) -> None:
    clock = MovableClock()
    gone = ProviderBadRequest("404 model_not_found: the model does not exist")
    groq = FakeProvider("groq", [gone, reply("a"), reply("b")])
    gateway = build_gateway(db, clock, groq=groq)
    assert gateway.chat(Task.chat_agent, prompt()).model == GROQ_120B
    assert gateway.chat(Task.chat_agent, prompt()).model == GROQ_120B
    assert [c.model for c in groq.calls] == [GROQ_70B, GROQ_120B, GROQ_120B]
    assert availability(gateway.status(), GROQ_70B)["reason"] == "model_unavailable"


def test_a_retired_gemini_model_is_parked_like_any_missing_model(db: Session) -> None:
    clock = MovableClock()
    gone = ProviderBadRequest("404 NOT_FOUND: no longer available to new users")
    google = FakeProvider("google", [gone, reply("ok")])
    gateway = build_gateway(db, clock, google=google)
    assert gateway.chat(Task.chat_agent, prompt()).model == "gemini-3.1-flash-lite"
    assert availability(gateway.status(), GEMINI_LITE)["reason"] == "model_unavailable"
