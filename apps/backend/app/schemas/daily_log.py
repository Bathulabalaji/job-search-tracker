from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, PatchModel

Count = Annotated[int, Field(ge=0, le=10_000)]
Hours = Annotated[float, Field(ge=0, le=24)]


class DailyLogCreate(BaseModel):
    log_date: date | None = None  # defaults to today
    applications_sent: Count = 0
    messages_sent: Count = 0
    referrals_requested: Count = 0
    problems_solved: Count = 0
    mocks_done: Count = 0
    hours_prep: Hours = 0
    notes: str | None = Field(default=None, max_length=4000)


class DailyLogUpdate(PatchModel):
    non_nullable = frozenset(
        {
            "applications_sent",
            "messages_sent",
            "referrals_requested",
            "problems_solved",
            "mocks_done",
            "hours_prep",
        }
    )

    applications_sent: Count | None = None
    messages_sent: Count | None = None
    referrals_requested: Count | None = None
    problems_solved: Count | None = None
    mocks_done: Count | None = None
    hours_prep: Hours | None = None
    notes: str | None = Field(default=None, max_length=4000)


class DailyLogRead(ORMModel):
    id: int
    log_date: date
    applications_sent: int
    messages_sent: int
    referrals_requested: int
    problems_solved: int
    mocks_done: int
    hours_prep: float
    notes: str | None


class StreakRead(BaseModel):
    today: date  # server's idea of today, so the UI never disagrees with the streak maths
    current: int
    longest: int
    logged_today: bool
    last_active_date: date | None
