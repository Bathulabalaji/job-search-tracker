from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.models.enums import Stage
from app.repositories.analytics import AnalyticsRepository
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    NextAction,
    SummaryResponse,
    TodayFollowup,
    TodayInterview,
    TodayResponse,
)
from app.services import rules
from app.services.analytics_math import applied_and_responded, ratio, week_start

TOP_NEXT_ACTIONS = 3


class DashboardService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.clock = clock
        self.repo = DashboardRepository(session)
        self.analytics = AnalyticsRepository(session)

    def today(self) -> TodayResponse:
        today = self.clock.today()
        start = datetime.combine(today, time.min, tzinfo=self.clock.tz)
        end = start + timedelta(days=1)

        followups = [
            TodayFollowup(
                id=f.id,
                opportunity_id=o.id,
                company=o.company,
                role=o.role,
                due_date=f.due_date,
                channel=f.channel,
                message_draft=f.message_draft,
                days_overdue=(today - f.due_date).days,
            )
            for f, o in self.repo.due_followups(today)
        ]
        interviews = [
            TodayInterview(
                interaction_id=i.id,
                opportunity_id=o.id,
                company=o.company,
                role=o.role,
                occurred_at=i.occurred_at,
                summary=i.summary,
            )
            for i, o in self.repo.interviews_between(start, end)
        ]
        next_actions = [
            NextAction(
                opportunity_id=o.id,
                company=o.company,
                role=o.role,
                stage=o.stage,
                priority=o.priority,
                next_action=o.next_action or "",
                next_action_due=o.next_action_due,
                overdue=o.next_action_due is not None and o.next_action_due < today,
            )
            for o in self.repo.open_with_next_action(rules.CLOSED_STAGES, TOP_NEXT_ACTIONS)
        ]
        return TodayResponse(
            today=today, followups=followups, interviews=interviews, next_actions=next_actions
        )

    def summary(self) -> SummaryResponse:
        counts = {stage: 0 for stage in Stage} | self.analytics.stage_counts()
        applied, responded = applied_and_responded(self.analytics.opportunity_progress())

        monday = week_start(self.clock.today())
        start = datetime.combine(monday, time.min, tzinfo=self.clock.tz)
        interviews = self.analytics.interview_times(start, start + timedelta(days=7))
        return SummaryResponse(
            counts_per_stage=counts,
            total=sum(counts.values()),
            applied_total=applied,
            responded_total=responded,
            response_rate=ratio(responded, applied),
            interviews_this_week=len(interviews),
        )
