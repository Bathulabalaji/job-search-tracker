from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import Direction, FollowupStatus, InteractionType, Stage
from app.models.followup import Followup
from app.models.interaction import Interaction
from app.schemas.interaction import InteractionCreate
from app.schemas.opportunity import MoveRequest, OpportunityCreate, OpportunityUpdate
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService


@pytest.fixture
def service(db: Session, clock: Clock, settings: Settings) -> OpportunityService:
    return OpportunityService(db, clock, settings)


def _followups(db: Session, opportunity_id: int) -> list[Followup]:
    return list(db.scalars(select(Followup).where(Followup.opportunity_id == opportunity_id)))


def _interactions(db: Session, opportunity_id: int) -> list[Interaction]:
    stmt = select(Interaction).where(Interaction.opportunity_id == opportunity_id)
    return list(db.scalars(stmt))


def _new(service: OpportunityService, stage: Stage = Stage.found) -> int:
    return service.create(
        OpportunityCreate(company="Acme", role="Backend Engineer", stage=stage)
    ).id


# ---- CRUD ----------------------------------------------------------------------------------


def test_create_applies_defaults(service: OpportunityService) -> None:
    opp = service.create(
        OpportunityCreate(company="Acme", role="Dev", stack_tags=["python", "fastapi"])
    )
    assert opp.stage == Stage.found
    assert opp.priority == 2
    assert opp.stack_tags == ["python", "fastapi"]
    assert opp.ghosted_suggestion is False


def test_update_changes_only_sent_fields(service: OpportunityService) -> None:
    opp_id = service.create(OpportunityCreate(company="Acme", role="Dev", fit_score=70)).id
    updated = service.update(opp_id, OpportunityUpdate(priority=1))
    assert updated.priority == 1
    assert updated.fit_score == 70
    assert updated.company == "Acme"


def test_update_can_clear_nullable_field(service: OpportunityService) -> None:
    opp_id = service.create(OpportunityCreate(company="Acme", role="Dev", fit_score=70)).id
    assert service.update(opp_id, OpportunityUpdate(fit_score=None)).fit_score is None


def test_update_rejects_null_for_required_field() -> None:
    with pytest.raises(ValueError, match="company cannot be null"):
        OpportunityUpdate.model_validate({"company": None})


def test_get_missing_raises(service: OpportunityService) -> None:
    with pytest.raises(NotFoundError):
        service.get(999_999)


def test_list_filters(service: OpportunityService) -> None:
    service.create(OpportunityCreate(company="Alpha", role="Dev", priority=1))
    service.create(OpportunityCreate(company="Beta", role="Dev", priority=3, stage=Stage.rejected))
    assert {o.company for o in service.list(priority=1)} == {"Alpha"}
    assert {o.company for o in service.list(stage=Stage.rejected)} == {"Beta"}
    assert {o.company for o in service.list(q="alph")} == {"Alpha"}


def test_delete_cascades_to_interactions_and_followups(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service)
    service.move(opp_id, MoveRequest(stage=Stage.applied))
    service.delete(opp_id)
    assert _interactions(db, opp_id) == []
    assert _followups(db, opp_id) == []


# ---- follow-up auto-rule --------------------------------------------------------------------


@pytest.mark.parametrize("stage", [Stage.applied, Stage.screening])
def test_create_in_trigger_stage_makes_followup_in_two_working_days(
    service: OpportunityService, db: Session, stage: Stage
) -> None:
    opp_id = _new(service, stage)
    (followup,) = _followups(db, opp_id)
    assert followup.due_date == date(2026, 11, 13)  # clock is Wed 11 Nov -> Fri 13 Nov
    assert followup.status == FollowupStatus.pending


@pytest.mark.parametrize("stage", [Stage.found, Stage.parked, Stage.rejected])
def test_create_in_other_stage_makes_no_followup(
    service: OpportunityService, db: Session, stage: Stage
) -> None:
    assert _followups(db, _new(service, stage)) == []


def test_move_to_applied_creates_followup(service: OpportunityService, db: Session) -> None:
    opp_id = _new(service)
    result = service.move(opp_id, MoveRequest(stage=Stage.applied))
    assert result.followup_created is not None
    assert result.followup_created.due_date == date(2026, 11, 13)
    assert len(_followups(db, opp_id)) == 1


def test_followup_due_date_skips_weekend(db: Session, settings: Settings) -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    thursday = datetime(2026, 11, 12, 5, 0, tzinfo=UTC)
    svc = OpportunityService(db, Clock(ZoneInfo(settings.timezone), lambda: thursday), settings)
    opp_id = _new(svc, Stage.applied)
    (followup,) = _followups(db, opp_id)
    assert followup.due_date == date(2026, 11, 16)  # Thu + 2 working days = Mon


def test_applied_then_screening_does_not_duplicate_pending_followup(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service, Stage.applied)
    result = service.move(opp_id, MoveRequest(stage=Stage.screening))
    assert result.followup_created is None
    assert len(_followups(db, opp_id)) == 1


def test_screening_creates_new_followup_once_previous_is_done(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service, Stage.applied)
    (first,) = _followups(db, opp_id)
    first.status = FollowupStatus.done
    db.flush()
    result = service.move(opp_id, MoveRequest(stage=Stage.screening))
    assert result.followup_created is not None
    assert len(_followups(db, opp_id)) == 2


def test_move_to_non_trigger_stage_makes_no_followup(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service)
    result = service.move(opp_id, MoveRequest(stage=Stage.parked))
    assert result.followup_created is None
    assert _followups(db, opp_id) == []


# ---- move ----------------------------------------------------------------------------------


def test_move_changes_stage_and_records_interaction(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service)
    result = service.move(opp_id, MoveRequest(stage=Stage.applied, note="Via careers page"))

    assert result.opportunity.stage == Stage.applied
    assert result.interaction.type == InteractionType.stage_change
    assert result.interaction.direction == Direction.out
    assert result.interaction.summary == "Stage: found → applied. Via careers page"
    assert len(_interactions(db, opp_id)) == 1


def test_move_to_same_stage_is_conflict_and_writes_nothing(
    service: OpportunityService, db: Session
) -> None:
    opp_id = _new(service, Stage.applied)
    with pytest.raises(ConflictError):
        service.move(opp_id, MoveRequest(stage=Stage.applied))
    assert _interactions(db, opp_id) == []


def test_move_missing_opportunity_raises(service: OpportunityService) -> None:
    with pytest.raises(NotFoundError):
        service.move(999_999, MoveRequest(stage=Stage.applied))


# ---- days since contact / ghosted suggestion ------------------------------------------------


def _log(db: Session, clock: Clock, opp_id: int, days_ago: int, kind: InteractionType) -> None:
    InteractionService(db, clock).create(
        InteractionCreate(
            opportunity_id=opp_id, type=kind, occurred_at=clock.now() - timedelta(days=days_ago)
        )
    )


def test_ghost_suggested_after_21_days_without_contact(
    service: OpportunityService, db: Session, clock: Clock
) -> None:
    opp_id = _new(service, Stage.applied)
    _log(db, clock, opp_id, 21, InteractionType.email)
    opp = service.get(opp_id)
    assert opp.days_since_contact == 21
    assert opp.ghosted_suggestion is True


def test_not_ghosted_at_20_days(service: OpportunityService, db: Session, clock: Clock) -> None:
    opp_id = _new(service, Stage.applied)
    _log(db, clock, opp_id, 20, InteractionType.email)
    assert service.get(opp_id).ghosted_suggestion is False


def test_recent_contact_resets_the_clock(
    service: OpportunityService, db: Session, clock: Clock
) -> None:
    opp_id = _new(service, Stage.interviewing)
    _log(db, clock, opp_id, 40, InteractionType.email)
    _log(db, clock, opp_id, 2, InteractionType.call)
    opp = service.get(opp_id)
    assert opp.days_since_contact == 2
    assert opp.ghosted_suggestion is False


def test_stage_change_does_not_count_as_contact(
    service: OpportunityService, db: Session, clock: Clock
) -> None:
    opp_id = _new(service, Stage.found)
    _log(db, clock, opp_id, 30, InteractionType.email)
    service.move(opp_id, MoveRequest(stage=Stage.applied))  # stage_change dated "now"
    opp = service.get(opp_id)
    assert opp.days_since_contact == 30
    assert opp.ghosted_suggestion is True


def test_no_interactions_counts_from_creation(service: OpportunityService) -> None:
    opp = service.get(_new(service, Stage.applied))
    assert opp.last_contact_at is None
    assert opp.days_since_contact == 0


def test_ghost_suggestion_is_not_applied_automatically(
    service: OpportunityService, db: Session, clock: Clock
) -> None:
    opp_id = _new(service, Stage.applied)
    _log(db, clock, opp_id, 60, InteractionType.email)
    assert service.get(opp_id).stage == Stage.applied
