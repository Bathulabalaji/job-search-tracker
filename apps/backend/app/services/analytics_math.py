"""Pure analytics maths (no database): funnel, response rates, streaks, week boundaries."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.models.enums import Source, Stage

# Funnel steps in order. Rejected, ghosted and parked are exits, not steps: how far an
# opportunity got is judged from the stages it has actually been in.
FUNNEL_STEPS: tuple[tuple[str, str, frozenset[Stage]], ...] = (
    ("found", "Found", frozenset({Stage.found})),
    ("applied", "Applied", frozenset({Stage.applied})),
    ("screening", "Screening", frozenset({Stage.screening})),
    ("interview", "Interview", frozenset({Stage.interview_scheduled, Stage.interviewing})),
    ("offer", "Offer", frozenset({Stage.offer})),
    ("accepted", "Accepted", frozenset({Stage.accepted})),
)
APPLIED_STEP = 1
INTERVIEW_STEP = 3
OFFER_STEP = 4


@dataclass(frozen=True)
class OpportunityProgress:
    source: Source
    visited: frozenset[Stage]  # current stage plus every stage it moved from or to
    responded: bool  # has at least one inbound (non-system) interaction


@dataclass(frozen=True)
class FunnelCount:
    key: str
    label: str
    count: int
    conversion_from_previous: float | None
    conversion_from_start: float | None


def step_index(stage: Stage) -> int | None:
    for index, (_, _, stages) in enumerate(FUNNEL_STEPS):
        if stage in stages:
            return index
    return None


def furthest_step(visited: Iterable[Stage]) -> int:
    """Highest funnel step reached. Every opportunity was at least 'found'."""
    indexes = [i for stage in visited if (i := step_index(stage)) is not None]
    return max(indexes, default=0)


def ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def build_funnel(progress: Iterable[OpportunityProgress]) -> list[FunnelCount]:
    furthest = [furthest_step(p.visited) for p in progress]
    counts = [sum(1 for f in furthest if f >= i) for i in range(len(FUNNEL_STEPS))]
    result: list[FunnelCount] = []
    for index, (key, label, _) in enumerate(FUNNEL_STEPS):
        previous = counts[index - 1] if index > 0 else None
        result.append(
            FunnelCount(
                key=key,
                label=label,
                count=counts[index],
                conversion_from_previous=None
                if previous is None
                else ratio(counts[index], previous),
                conversion_from_start=ratio(counts[index], counts[0]),
            )
        )
    return result


def applied_and_responded(progress: Iterable[OpportunityProgress]) -> tuple[int, int]:
    """(opportunities that reached Applied or beyond, how many of those got a reply)."""
    applied = [p for p in progress if furthest_step(p.visited) >= APPLIED_STEP]
    return len(applied), sum(1 for p in applied if p.responded)


def week_start(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def percent_of_target(actual: float, target: int | None) -> float | None:
    if target is None or target == 0:
        return None
    return round(actual / target * 100, 1)


def compute_streaks(active_days: set[date], today: date) -> tuple[int, int]:
    """(current, longest) runs of consecutive active days.

    The current streak is not broken until a whole day passes: if today has no activity
    yet it counts back from yesterday.
    """
    anchor = today if today in active_days else today - timedelta(days=1)
    current = 0
    day = anchor
    while day in active_days:
        current += 1
        day -= timedelta(days=1)

    longest = 0
    run = 0
    previous: date | None = None
    for day in sorted(active_days):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return current, longest
