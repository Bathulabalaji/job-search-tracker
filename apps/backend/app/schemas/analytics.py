from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.enums import Source
from app.schemas.weekly_target import WeeklyTargetRead

Metric = Literal["applications", "messages", "referrals", "problems", "mocks", "interviews"]


class WeeklyTotals(BaseModel):
    applications: int
    messages: int
    referrals: int
    problems: int
    mocks: int
    interviews: int
    hours_prep: float


class MetricProgress(BaseModel):
    metric: Metric
    label: str
    actual: int
    target: int | None
    percent: float | None  # actual / target * 100; may exceed 100; null when there is no target


class DailyPoint(BaseModel):
    date: date
    applications: int
    messages: int
    referrals: int
    problems: int
    mocks: int
    hours_prep: float


class WeekTrendPoint(BaseModel):
    week_start: date
    applications: int
    messages: int
    referrals: int
    problems: int
    mocks: int
    interviews: int


class FunnelStepRead(BaseModel):
    key: str
    label: str
    count: int
    conversion_from_previous: float | None
    conversion_from_start: float | None


class SourceResponse(BaseModel):
    source: Source
    applied: int
    responded: int
    response_rate: float | None


class Scorecard(BaseModel):
    applications_total: int  # opportunities that reached Applied or beyond
    response_rate: float | None
    interview_rate: float | None  # reached Interview / reached Applied
    offers: int
    active_opportunities: int
    current_streak: int


class WeeklyAnalytics(BaseModel):
    week_start: date
    week_end: date
    is_current_week: bool
    target: WeeklyTargetRead | None
    target_carried_over: bool  # true when `target` is an earlier week's, reused
    totals: WeeklyTotals
    progress: list[MetricProgress]
    daily: list[DailyPoint]
    trend: list[WeekTrendPoint]
    funnel: list[FunnelStepRead]
    response_by_source: list[SourceResponse]
    scorecard: Scorecard
