from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import FollowupChannel, Stage


class TodayFollowup(BaseModel):
    id: int
    opportunity_id: int
    company: str
    role: str
    due_date: date
    channel: FollowupChannel
    message_draft: str | None
    days_overdue: int  # 0 = due today


class TodayInterview(BaseModel):
    interaction_id: int
    opportunity_id: int
    company: str
    role: str
    occurred_at: datetime
    summary: str | None


class NextAction(BaseModel):
    opportunity_id: int
    company: str
    role: str
    stage: Stage
    priority: int
    next_action: str
    next_action_due: date | None
    overdue: bool


class TodayResponse(BaseModel):
    today: date
    followups: list[TodayFollowup]
    interviews: list[TodayInterview]
    next_actions: list[NextAction]


class SummaryResponse(BaseModel):
    counts_per_stage: dict[Stage, int]
    total: int
    applied_total: int
    responded_total: int
    response_rate: float | None
    interviews_this_week: int
