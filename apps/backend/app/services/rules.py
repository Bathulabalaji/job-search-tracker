"""Pure business rules (no database access) so they are trivial to unit test."""

from datetime import date, datetime, timedelta

from app.models.enums import Stage

# Entering one of these stages creates a follow-up.
AUTO_FOLLOWUP_STAGES: frozenset[Stage] = frozenset({Stage.applied, Stage.screening})

# Stages where silence is meaningful, so a 'ghosted' suggestion can be raised.
ACTIVE_STAGES: frozenset[Stage] = frozenset(
    {Stage.applied, Stage.screening, Stage.interview_scheduled, Stage.interviewing}
)


def add_working_days(start: date, days: int) -> date:
    """Add Mon-Fri working days. Public holidays are not modelled."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def days_since(moment: datetime, now: datetime) -> int:
    return max((now - moment).days, 0)


def is_ghost_suggested(stage: Stage, days_since_contact: int, threshold_days: int) -> bool:
    return stage in ACTIVE_STAGES and days_since_contact >= threshold_days
