"""Pure business rules (no database access) so they are trivial to unit test."""

from datetime import date, datetime, timedelta

from app.models.enums import Stage

# Entering one of these stages creates a follow-up.
AUTO_FOLLOWUP_STAGES: frozenset[Stage] = frozenset({Stage.applied, Stage.screening})

# Stages where silence is meaningful, so a 'ghosted' suggestion can be raised.
ACTIVE_STAGES: frozenset[Stage] = frozenset(
    {Stage.applied, Stage.screening, Stage.interview_scheduled, Stage.interviewing}
)


# Stages where the search for this opportunity is over (or paused).
CLOSED_STAGES: frozenset[Stage] = frozenset(
    {Stage.accepted, Stage.rejected, Stage.ghosted, Stage.parked}
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


def working_days_between(start: date, end: date) -> int:
    """Mon-Fri days from `start` (exclusive) to `end` (inclusive); 0 when `end` is not later."""
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


# Message cadence (see messaging/suggest.py). Working days, because nobody answers on a Sunday.
FIRST_FOLLOW_UP_AFTER = 5  # applied with no reply
NEXT_FOLLOW_UP_AFTER = 7  # between follow-ups
INTERVIEW_NUDGE_AFTER = 5  # an interview with no update
THANK_YOU_WINDOW_DAYS = 3  # a thank-you is still welcome this long after a call or interview
CONTACT_COOLDOWN_DAYS = 3  # never message the same person twice inside this many days
MAX_UNANSWERED_TOUCHES = 3  # after this, stop and suggest marking it ghosted
