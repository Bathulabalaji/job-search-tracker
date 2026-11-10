from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import Direction, InteractionType, PrepCategory, PrepStatus, Source, Stage
from app.schemas.daily_log import DailyLogCreate, DailyLogUpdate
from app.schemas.interaction import InteractionCreate
from app.schemas.opportunity import MoveRequest, OpportunityCreate
from app.schemas.prep_item import PrepItemCreate, PrepItemUpdate
from app.schemas.weekly_target import WeeklyTargetCreate, WeeklyTargetUpdate
from app.services.analytics import AnalyticsService
from app.services.daily_log import DailyLogService
from app.services.dashboard import DashboardService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService
from app.services.prep_item import PrepItemService
from app.services.weekly_target import WeeklyTargetService

TODAY = date(2026, 11, 11)  # Wednesday
MONDAY = date(2026, 11, 9)


# ---- daily logs ---------------------------------------------------------------------------


def test_daily_log_defaults_to_today_and_zero_counts(db: Session, clock: Clock) -> None:
    log = DailyLogService(db, clock).create(DailyLogCreate())
    assert log.log_date == TODAY
    assert (log.applications_sent, log.hours_prep) == (0, 0)


def test_daily_log_rejects_duplicate_date(db: Session, clock: Clock) -> None:
    svc = DailyLogService(db, clock)
    svc.create(DailyLogCreate(log_date=TODAY, applications_sent=3))
    with pytest.raises(ConflictError):
        svc.create(DailyLogCreate(log_date=TODAY))


def test_daily_log_update_changes_only_sent_fields(db: Session, clock: Clock) -> None:
    svc = DailyLogService(db, clock)
    log = svc.create(DailyLogCreate(applications_sent=3, messages_sent=5))
    updated = svc.update(log.id, DailyLogUpdate(messages_sent=9))
    assert (updated.applications_sent, updated.messages_sent) == (3, 9)


@pytest.mark.parametrize("bad", [{"applications_sent": -1}, {"hours_prep": 25}])
def test_daily_log_validates_ranges(bad: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        DailyLogCreate.model_validate(bad)


def test_daily_log_missing_raises(db: Session, clock: Clock) -> None:
    with pytest.raises(NotFoundError):
        DailyLogService(db, clock).get(999_999)


def test_streak_counts_active_days_only(db: Session, clock: Clock) -> None:
    svc = DailyLogService(db, clock)
    svc.create(DailyLogCreate(log_date=TODAY, problems_solved=2))
    svc.create(DailyLogCreate(log_date=TODAY - timedelta(days=1), hours_prep=1.5))
    # A log full of zeros is a rest day: it must not extend the streak.
    svc.create(DailyLogCreate(log_date=TODAY - timedelta(days=2)))
    svc.create(DailyLogCreate(log_date=TODAY - timedelta(days=3), applications_sent=1))

    streak = svc.streak()

    assert (streak.current, streak.longest) == (2, 2)
    assert streak.logged_today is True
    assert streak.last_active_date == TODAY


def test_streak_survives_until_the_day_ends(db: Session, clock: Clock) -> None:
    svc = DailyLogService(db, clock)
    svc.create(DailyLogCreate(log_date=TODAY - timedelta(days=1), mocks_done=1))
    streak = svc.streak()
    assert (streak.current, streak.logged_today) == (1, False)


# ---- weekly targets -----------------------------------------------------------------------


def test_weekly_target_must_start_on_monday() -> None:
    with pytest.raises(ValidationError, match="Monday"):
        WeeklyTargetCreate(week_start=TODAY)  # a Wednesday


def test_weekly_target_one_per_week(db: Session) -> None:
    svc = WeeklyTargetService(db)
    svc.create(WeeklyTargetCreate(week_start=MONDAY, applications=10))
    with pytest.raises(ConflictError):
        svc.create(WeeklyTargetCreate(week_start=MONDAY))


def test_weekly_target_update(db: Session) -> None:
    svc = WeeklyTargetService(db)
    target = svc.create(WeeklyTargetCreate(week_start=MONDAY, applications=10, messages=20))
    updated = svc.update(target.id, WeeklyTargetUpdate(applications=12))
    assert (updated.applications, updated.messages) == (12, 20)


# ---- prep items ---------------------------------------------------------------------------


def test_prep_item_crud_and_filters(db: Session) -> None:
    svc = PrepItemService(db)
    a = svc.create(PrepItemCreate(topic="Async SQLAlchemy", category=PrepCategory.python))
    svc.create(PrepItemCreate(topic="Indexes", category=PrepCategory.db, status=PrepStatus.done))

    assert a.status == PrepStatus.todo and a.confidence == 1
    svc.update(a.id, PrepItemUpdate(status=PrepStatus.doing, confidence=4))
    assert [i.topic for i in svc.list(category=PrepCategory.python)] == ["Async SQLAlchemy"]
    assert [i.topic for i in svc.list(status=PrepStatus.done)] == ["Indexes"]
    assert [i.topic for i in svc.list(q="async")] == ["Async SQLAlchemy"]
    svc.delete(a.id)
    with pytest.raises(NotFoundError):
        svc.get(a.id)


def test_prep_confidence_is_1_to_5() -> None:
    with pytest.raises(ValidationError):
        PrepItemCreate(topic="x", category=PrepCategory.ai, confidence=6)
    with pytest.raises(ValidationError):
        PrepItemUpdate(confidence=0)


# ---- analytics ----------------------------------------------------------------------------


@pytest.fixture
def analytics(db: Session, clock: Clock) -> AnalyticsService:
    return AnalyticsService(db, clock)


def _log(db: Session, clock: Clock, day: date, **counts: float) -> None:
    DailyLogService(db, clock).create(DailyLogCreate(log_date=day, **counts))


def test_weekly_totals_zero_fill_and_progress(
    analytics: AnalyticsService, db: Session, clock: Clock
) -> None:
    _log(db, clock, MONDAY, applications_sent=4, messages_sent=10, hours_prep=2.5)
    _log(db, clock, TODAY, applications_sent=3, problems_solved=5, hours_prep=1.0)
    _log(db, clock, MONDAY - timedelta(days=1), applications_sent=99)  # previous week: excluded
    WeeklyTargetService(db).create(
        WeeklyTargetCreate(week_start=MONDAY, applications=10, messages=20, problems=5)
    )

    result = analytics.weekly()

    assert (result.week_start, result.week_end) == (MONDAY, date(2026, 11, 15))
    assert len(result.daily) == 7
    assert [p.applications for p in result.daily] == [4, 0, 3, 0, 0, 0, 0]
    assert result.totals.applications == 7
    assert result.totals.hours_prep == 3.5
    by_metric = {p.metric: p for p in result.progress}
    assert (by_metric["applications"].actual, by_metric["applications"].percent) == (7, 70.0)
    assert by_metric["messages"].percent == 50.0
    assert by_metric["problems"].percent == 100.0
    assert by_metric["referrals"].percent is None  # target 0 -> no percentage
    assert result.target_carried_over is False


def test_target_is_carried_over_from_an_earlier_week(
    analytics: AnalyticsService, db: Session
) -> None:
    WeeklyTargetService(db).create(
        WeeklyTargetCreate(week_start=MONDAY - timedelta(weeks=3), applications=8)
    )
    result = analytics.weekly()
    assert result.target is not None and result.target.applications == 8
    assert result.target_carried_over is True


def test_no_target_means_no_percentages(analytics: AnalyticsService) -> None:
    result = analytics.weekly()
    assert result.target is None
    assert all(p.target is None and p.percent is None for p in result.progress)


def test_week_of_is_normalised_to_monday(analytics: AnalyticsService) -> None:
    assert analytics.weekly(date(2026, 11, 14)).week_start == MONDAY


def test_trend_has_eight_weeks_ending_on_selected_week(
    analytics: AnalyticsService, db: Session, clock: Clock
) -> None:
    _log(db, clock, MONDAY - timedelta(weeks=2), applications_sent=6)
    _log(db, clock, TODAY, applications_sent=2)
    trend = analytics.weekly().trend
    assert len(trend) == 8
    assert trend[-1].week_start == MONDAY
    assert [t.applications for t in trend][-3:] == [6, 0, 2]


def test_interviews_come_from_interactions(
    analytics: AnalyticsService, db: Session, clock: Clock, settings: Settings
) -> None:
    opp = OpportunityService(db, clock, settings).create(OpportunityCreate(company="A", role="B"))
    interactions = InteractionService(db, clock)
    this_week = datetime(2026, 11, 12, 5, 0, tzinfo=UTC)
    last_week = this_week - timedelta(days=7)
    for moment in (this_week, last_week):
        interactions.create(
            InteractionCreate(
                opportunity_id=opp.id, type=InteractionType.interview, occurred_at=moment
            )
        )
    interactions.create(  # a call is not an interview
        InteractionCreate(opportunity_id=opp.id, type=InteractionType.call, occurred_at=this_week)
    )

    result = analytics.weekly()

    assert result.totals.interviews == 1
    assert result.trend[-2].interviews == 1


def _funnel_fixture(db: Session, clock: Clock, settings: Settings) -> None:
    svc = OpportunityService(db, clock, settings)
    interactions = InteractionService(db, clock)

    def create(company: str, source: Source) -> int:
        return svc.create(OpportunityCreate(company=company, role="Dev", source=source)).id

    never_applied = create("Never", Source.linkedin)
    del never_applied
    replied = create("Replied", Source.referral)
    svc.move(replied, MoveRequest(stage=Stage.applied))
    interactions.create(
        InteractionCreate(
            opportunity_id=replied, type=InteractionType.email, direction=Direction.in_
        )
    )
    svc.move(replied, MoveRequest(stage=Stage.screening))
    svc.move(replied, MoveRequest(stage=Stage.interview_scheduled))
    svc.move(replied, MoveRequest(stage=Stage.offer))

    silent = create("Silent", Source.linkedin)
    svc.move(silent, MoveRequest(stage=Stage.applied))

    rejected = create("Rejected", Source.linkedin)
    svc.move(rejected, MoveRequest(stage=Stage.applied))
    svc.move(rejected, MoveRequest(stage=Stage.screening))
    interactions.create(
        InteractionCreate(
            opportunity_id=rejected, type=InteractionType.call, direction=Direction.in_
        )
    )
    svc.move(rejected, MoveRequest(stage=Stage.rejected))


def test_funnel_uses_stage_history_so_rejections_keep_credit(
    analytics: AnalyticsService, db: Session, clock: Clock, settings: Settings
) -> None:
    _funnel_fixture(db, clock, settings)
    funnel = {s.key: s for s in analytics.weekly().funnel}

    assert [funnel[k].count for k in ("found", "applied", "screening", "interview", "offer")] == [
        4,
        3,
        2,
        1,
        1,
    ]
    assert funnel["applied"].conversion_from_previous == 0.75
    assert funnel["screening"].conversion_from_previous == pytest.approx(2 / 3)


def test_response_rate_by_source_and_scorecard(
    analytics: AnalyticsService, db: Session, clock: Clock, settings: Settings
) -> None:
    _funnel_fixture(db, clock, settings)
    _log(db, clock, TODAY, applications_sent=1)
    result = analytics.weekly()

    by_source = {s.source: s for s in result.response_by_source}
    assert (by_source[Source.referral].applied, by_source[Source.referral].responded) == (1, 1)
    assert by_source[Source.linkedin].applied == 2
    assert by_source[Source.linkedin].response_rate == 0.5
    assert by_source[Source.walkin].response_rate is None

    card = result.scorecard
    assert card.applications_total == 3
    assert card.response_rate == pytest.approx(2 / 3)
    assert card.interview_rate == pytest.approx(1 / 3)
    assert card.offers == 1
    assert card.active_opportunities == 3  # Never (found), Replied (offer), Silent (applied)
    assert card.current_streak == 1


# ---- dashboard summary --------------------------------------------------------------------


def test_summary_counts_every_stage_and_interviews_this_week(
    db: Session, clock: Clock, settings: Settings
) -> None:
    _funnel_fixture(db, clock, settings)
    opp_id = OpportunityService(db, clock, settings).list(q="Silent")[0].id
    InteractionService(db, clock).create(
        InteractionCreate(
            opportunity_id=opp_id,
            type=InteractionType.interview,
            occurred_at=datetime(2026, 11, 13, 5, 0, tzinfo=UTC),  # Friday
        )
    )

    summary = DashboardService(db, clock).summary()

    assert set(summary.counts_per_stage) == set(Stage)
    assert summary.counts_per_stage[Stage.found] == 1
    assert summary.counts_per_stage[Stage.rejected] == 1
    assert summary.total == 4
    assert (summary.applied_total, summary.responded_total) == (3, 2)
    assert summary.response_rate == pytest.approx(2 / 3)
    assert summary.interviews_this_week == 1


def test_move_records_structured_stage_history(
    db: Session, clock: Clock, settings: Settings
) -> None:
    svc = OpportunityService(db, clock, settings)
    opp_id = svc.create(OpportunityCreate(company="A", role="B")).id
    result = svc.move(opp_id, MoveRequest(stage=Stage.applied))
    assert (result.interaction.from_stage, result.interaction.to_stage) == (
        Stage.found,
        Stage.applied,
    )
