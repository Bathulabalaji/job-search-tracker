from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel, PatchModel

Target = Annotated[int, Field(ge=0, le=10_000)]


class WeeklyTargetCreate(BaseModel):
    week_start: date
    applications: Target = 0
    messages: Target = 0
    referrals: Target = 0
    problems: Target = 0
    mocks: Target = 0
    interviews: Target = 0

    @model_validator(mode="after")
    def _must_be_monday(self) -> Self:
        if self.week_start.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        return self


class WeeklyTargetUpdate(PatchModel):
    non_nullable = frozenset(
        {"applications", "messages", "referrals", "problems", "mocks", "interviews"}
    )

    applications: Target | None = None
    messages: Target | None = None
    referrals: Target | None = None
    problems: Target | None = None
    mocks: Target | None = None
    interviews: Target | None = None


class WeeklyTargetRead(ORMModel):
    id: int
    week_start: date
    applications: int
    messages: int
    referrals: int
    problems: int
    mocks: int
    interviews: int
