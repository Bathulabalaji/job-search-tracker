import pytest

from app.llm.usage_report import rollup
from app.repositories.provider_ledger import UsageRow


def row(model: str, task: str, outcome: str, calls: int, p: int, c: int, ms: int) -> UsageRow:
    return UsageRow("groq", model, task, outcome, calls, p, c, ms)


ROWS = [
    row("a", "chat.agent", "ok", 8, 8000, 800, 100),
    row("a", "chat.agent", "rate_limited", 2, 0, 0, 300),
    row("a", "guardrail", "ok", 10, 3000, 200, 50),
    row("b", "chat.agent", "ok", 5, 5000, 500, 200),
]


def test_rolls_up_by_the_chosen_dimensions_biggest_first() -> None:
    by_model = rollup(ROWS, ["model"])
    assert [(r.keys, r.calls, r.errors) for r in by_model] == [(("a",), 20, 2), (("b",), 5, 0)]
    first = by_model[0]
    assert first.prompt_tokens == 11000 and first.completion_tokens == 1000
    assert first.avg_latency_ms == round((100 * 8 + 300 * 2 + 50 * 10) / 20)

    by_both = rollup(ROWS, ["model", "task"])
    assert len(by_both) == 3 and by_both[0].keys == ("a", "chat.agent")


def test_cost_only_appears_when_prices_are_given() -> None:
    [a, _] = rollup(ROWS, ["model"])
    assert a.cost(None, None) is None
    # 11,000 in and 1,000 out at $0.50 / $1.50 per million tokens
    assert a.cost(0.5, 1.5) == pytest.approx(0.0055 + 0.0015)
    assert a.cost(0.5, None) == pytest.approx(0.0055)


def test_unknown_dimensions_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown dimension 'user'"):
        rollup(ROWS, ["user"])
