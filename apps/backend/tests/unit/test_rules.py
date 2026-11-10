from datetime import UTC, date, datetime

import pytest

from app.models.enums import Stage
from app.services.rules import add_working_days, days_since, is_ghost_suggested


@pytest.mark.parametrize(
    ("start", "days", "expected"),
    [
        (date(2026, 11, 9), 2, date(2026, 11, 11)),  # Mon + 2 = Wed
        (date(2026, 11, 11), 2, date(2026, 11, 13)),  # Wed + 2 = Fri
        (date(2026, 11, 12), 2, date(2026, 11, 16)),  # Thu + 2 = Mon (skips weekend)
        (date(2026, 11, 13), 2, date(2026, 11, 17)),  # Fri + 2 = Tue
        (date(2026, 11, 14), 2, date(2026, 11, 17)),  # Sat + 2 = Tue
        (date(2026, 11, 15), 1, date(2026, 11, 16)),  # Sun + 1 = Mon
        (date(2026, 11, 11), 0, date(2026, 11, 11)),
    ],
)
def test_add_working_days(start: date, days: int, expected: date) -> None:
    assert add_working_days(start, days) == expected


def test_days_since_never_negative() -> None:
    now = datetime(2026, 11, 11, tzinfo=UTC)
    assert days_since(datetime(2026, 11, 1, tzinfo=UTC), now) == 10
    assert days_since(datetime(2026, 11, 20, tzinfo=UTC), now) == 0


@pytest.mark.parametrize(
    ("stage", "days", "expected"),
    [
        (Stage.applied, 21, True),
        (Stage.applied, 20, False),
        (Stage.interviewing, 40, True),
        (Stage.found, 100, False),  # nothing sent yet, silence means nothing
        (Stage.rejected, 100, False),
        (Stage.ghosted, 100, False),  # already ghosted
        (Stage.offer, 100, False),
    ],
)
def test_is_ghost_suggested(stage: Stage, days: int, expected: bool) -> None:
    assert is_ghost_suggested(stage, days, threshold_days=21) is expected
