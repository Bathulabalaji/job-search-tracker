from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.models.enums import Source
from app.repositories.analytics import AnalyticsRepository
from app.repositories.daily_log import DailyLogRepository
from app.repositories.weekly_target import WeeklyTargetRepository
from app.schemas.analytics import (
    DailyPoint,
    FunnelStepRead,
    Metric,
    MetricProgress,
    Scorecard,
    SourceResponse,
    WeeklyAnalytics,
    WeeklyTotals,
    WeekTrendPoint,
)
from app.schemas.weekly_target import WeeklyTargetRead
from app.services import rules
from app.services.analytics_math import (
    INTERVIEW_STEP,
    OFFER_STEP,
    applied_and_responded,
    build_funnel,
    compute_streaks,
    furthest_step,
    percent_of_target,
    ratio,
    week_start,
)

TREND_WEEKS = 8
METRICS: tuple[tuple[Metric, str], ...] = (
    ("applications", "Applications"),
    ("messages", "Messages"),
    ("referrals", "Referrals"),
    ("problems", "Problems"),
    ("mocks", "Mocks"),
    ("interviews", "Interviews"),
)


class AnalyticsService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.clock = clock
        self.logs = DailyLogRepository(session)
        self.targets = WeeklyTargetRepository(session)
        self.analytics = AnalyticsRepository(session)

    def weekly(self, week_of: date | None = None) -> WeeklyAnalytics:
        today = self.clock.today()
        monday = week_start(week_of or today)
        sunday = monday + timedelta(days=6)
        trend_start = monday - timedelta(weeks=TREND_WEEKS - 1)

        logs = {log.log_date: log for log in self.logs.between(trend_start, sunday)}

        # Daily points for the selected week, zero-filled so charts show quiet days.
        daily: list[DailyPoint] = []
        for offset in range(7):
            day = monday + timedelta(days=offset)
            log = logs.get(day)
            daily.append(
                DailyPoint(
                    date=day,
                    applications=log.applications_sent if log else 0,
                    messages=log.messages_sent if log else 0,
                    referrals=log.referrals_requested if log else 0,
                    problems=log.problems_solved if log else 0,
                    mocks=log.mocks_done if log else 0,
                    hours_prep=log.hours_prep if log else 0.0,
                )
            )

        # Interviews per week come from interactions: daily logs have no interview column.
        interview_counts = Counter(
            week_start(moment.astimezone(self.clock.tz).date())
            for moment in self.analytics.interview_times(
                self._start_of(trend_start), self._start_of(sunday + timedelta(days=1))
            )
        )

        trend: list[WeekTrendPoint] = []
        for index in range(TREND_WEEKS):
            ws = trend_start + timedelta(weeks=index)
            week_logs = [logs[d] for d in (ws + timedelta(days=n) for n in range(7)) if d in logs]
            trend.append(
                WeekTrendPoint(
                    week_start=ws,
                    applications=sum(log.applications_sent for log in week_logs),
                    messages=sum(log.messages_sent for log in week_logs),
                    referrals=sum(log.referrals_requested for log in week_logs),
                    problems=sum(log.problems_solved for log in week_logs),
                    mocks=sum(log.mocks_done for log in week_logs),
                    interviews=interview_counts.get(ws, 0),
                )
            )

        totals = WeeklyTotals(
            applications=sum(p.applications for p in daily),
            messages=sum(p.messages for p in daily),
            referrals=sum(p.referrals for p in daily),
            problems=sum(p.problems for p in daily),
            mocks=sum(p.mocks for p in daily),
            interviews=interview_counts.get(monday, 0),
            hours_prep=round(sum(p.hours_prep for p in daily), 2),
        )

        # No target for this exact week? Reuse the most recent earlier one and say so.
        target = self.targets.get_by_week(monday)
        carried = False
        if target is None:
            target = self.targets.latest_on_or_before(monday)
            carried = target is not None

        progress: list[MetricProgress] = []
        for metric, label in METRICS:
            actual: int = getattr(totals, metric)
            goal: int | None = getattr(target, metric) if target else None
            progress.append(
                MetricProgress(
                    metric=metric,
                    label=label,
                    actual=actual,
                    target=goal,
                    percent=percent_of_target(actual, goal),
                )
            )

        opportunities = self.analytics.opportunity_progress()
        funnel = build_funnel(opportunities)
        applied_total, responded_total = applied_and_responded(opportunities)

        response_by_source: list[SourceResponse] = []
        for source in Source:
            applied, responded = applied_and_responded(
                [p for p in opportunities if p.source == source]
            )
            response_by_source.append(
                SourceResponse(
                    source=source,
                    applied=applied,
                    responded=responded,
                    response_rate=ratio(responded, applied),
                )
            )

        furthest = [furthest_step(p.visited) for p in opportunities]
        reached_interview = sum(1 for f in furthest if f >= INTERVIEW_STEP)
        stage_counts = self.analytics.stage_counts()
        current_streak, _ = compute_streaks(self.logs.active_dates(), today)
        scorecard = Scorecard(
            applications_total=applied_total,
            response_rate=ratio(responded_total, applied_total),
            interview_rate=ratio(reached_interview, applied_total),
            offers=sum(1 for f in furthest if f >= OFFER_STEP),
            active_opportunities=sum(
                count for stage, count in stage_counts.items() if stage not in rules.CLOSED_STAGES
            ),
            current_streak=current_streak,
        )

        return WeeklyAnalytics(
            week_start=monday,
            week_end=sunday,
            is_current_week=monday == week_start(today),
            target=WeeklyTargetRead.model_validate(target) if target else None,
            target_carried_over=carried,
            totals=totals,
            progress=progress,
            daily=daily,
            trend=trend,
            funnel=[FunnelStepRead(**vars(step)) for step in funnel],
            response_by_source=response_by_source,
            scorecard=scorecard,
        )

    def _start_of(self, day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=self.clock.tz)
