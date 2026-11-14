"""Roll provider usage rows up by provider, model and/or task, with an optional cost estimate.

The estimate exists so you can see what a month of traffic would cost once the free tiers are
outgrown. Prices are never built in (they change and differ per model): pass them in, in
dollars per million tokens.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.repositories.provider_ledger import UsageRow

DIMENSIONS = ("provider", "model", "task")


@dataclass(frozen=True)
class Rollup:
    keys: tuple[str, ...]
    calls: int
    errors: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: int

    def cost(self, price_in: float | None, price_out: float | None) -> float | None:
        if price_in is None and price_out is None:
            return None
        return (
            self.prompt_tokens * (price_in or 0.0) + self.completion_tokens * (price_out or 0.0)
        ) / 1_000_000


def rollup(rows: Sequence[UsageRow], by: Sequence[str]) -> list[Rollup]:
    unknown = [d for d in by if d not in DIMENSIONS]
    if unknown:
        raise ValueError(f"unknown dimension {unknown[0]!r}; choose from {', '.join(DIMENSIONS)}")
    groups: dict[tuple[str, ...], list[UsageRow]] = {}
    for row in rows:
        values = {"provider": row.provider, "model": row.resource, "task": row.task}
        groups.setdefault(tuple(values[d] for d in by), []).append(row)
    out: list[Rollup] = []
    for keys, members in groups.items():
        calls = sum(r.calls for r in members)
        out.append(
            Rollup(
                keys=keys,
                calls=calls,
                errors=sum(r.calls for r in members if r.outcome != "ok"),
                prompt_tokens=sum(r.prompt_tokens for r in members),
                completion_tokens=sum(r.completion_tokens for r in members),
                avg_latency_ms=(
                    round(sum(r.avg_latency_ms * r.calls for r in members) / calls) if calls else 0
                ),
            )
        )
    return sorted(out, key=lambda r: r.prompt_tokens + r.completion_tokens, reverse=True)
