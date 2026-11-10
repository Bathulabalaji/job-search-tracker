from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.models.enums import FollowupStatus, InteractionType, Stage
from app.models.followup import Followup
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity
from app.services.dashboard import DashboardService

TODAY = date(2026, 11, 11)  # clock fixture: Wed 11 Nov 2026, 10:00 IST


@pytest.fixture
def service(db: Session, clock: Clock) -> DashboardService:
    return DashboardService(db, clock)


def _opp(db: Session, **kwargs: object) -> Opportunity:
    opp = Opportunity(company=str(kwargs.pop("company", "Acme")), role="Dev", **kwargs)
    db.add(opp)
    db.flush()
    return opp


def _followup(db: Session, opp: Opportunity, due: date, status: FollowupStatus) -> None:
    db.add(Followup(opportunity_id=opp.id, due_date=due, status=status))
    db.flush()


def test_followups_include_overdue_and_due_today_only_when_pending(
    service: DashboardService, db: Session
) -> None:
    opp = _opp(db)
    _followup(db, opp, TODAY - timedelta(days=3), FollowupStatus.pending)
    _followup(db, opp, TODAY, FollowupStatus.pending)
    _followup(db, opp, TODAY + timedelta(days=1), FollowupStatus.pending)  # future
    _followup(db, opp, TODAY - timedelta(days=1), FollowupStatus.done)
    _followup(db, opp, TODAY - timedelta(days=1), FollowupStatus.skipped)

    result = service.today()

    assert result.today == TODAY
    assert [f.days_overdue for f in result.followups] == [3, 0]
    assert result.followups[0].company == "Acme"


def test_interviews_today_uses_local_day_boundaries(service: DashboardService, db: Session) -> None:
    opp = _opp(db)
    # IST day = 2026-11-10 18:30 UTC .. 2026-11-11 18:30 UTC
    inside = datetime(2026, 11, 11, 18, 0, tzinfo=UTC)  # 23:30 IST today
    before = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)  # 23:30 IST yesterday
    after = datetime(2026, 11, 11, 19, 0, tzinfo=UTC)  # 00:30 IST tomorrow
    for moment in (inside, before, after):
        db.add(
            Interaction(opportunity_id=opp.id, type=InteractionType.interview, occurred_at=moment)
        )
    db.add(  # right day but not an interview
        Interaction(opportunity_id=opp.id, type=InteractionType.call, occurred_at=inside)
    )
    db.flush()

    result = service.today()

    assert [i.occurred_at for i in result.interviews] == [inside]


def test_next_actions_top_three_ordered_and_exclude_closed(
    service: DashboardService, db: Session
) -> None:
    _opp(db, company="NoDue", next_action="Think", priority=1)
    _opp(db, company="Later", next_action="B", next_action_due=TODAY + timedelta(days=5))
    _opp(db, company="Overdue", next_action="A", next_action_due=TODAY - timedelta(days=2))
    _opp(db, company="DueToday", next_action="C", next_action_due=TODAY, priority=2)
    _opp(
        db,
        company="Closed",
        next_action="X",
        next_action_due=TODAY - timedelta(days=9),
        stage=Stage.rejected,
    )
    _opp(db, company="Blank", next_action=None, next_action_due=TODAY)

    result = service.today()

    assert [n.company for n in result.next_actions] == ["Overdue", "DueToday", "Later"]
    assert [n.overdue for n in result.next_actions] == [True, False, False]


def test_empty_day(service: DashboardService) -> None:
    result = service.today()
    assert (result.followups, result.interviews, result.next_actions) == ([], [], [])
