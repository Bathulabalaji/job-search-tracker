from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import NotFoundError
from app.models.enums import FollowupStatus, InteractionType
from app.models.opportunity import Opportunity
from app.schemas.contact import ContactCreate, ContactUpdate
from app.schemas.followup import FollowupCreate, FollowupUpdate
from app.schemas.interaction import InteractionCreate
from app.services.contact import ContactService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService


@pytest.fixture
def opp_id(db: Session) -> int:
    opp = Opportunity(user_id=db.info["user_id"], company="Acme", role="Dev")
    db.add(opp)
    db.flush()
    return opp.id


def test_followup_done_sets_and_clears_done_at(db: Session, clock: Clock, opp_id: int) -> None:
    svc = FollowupService(db, clock, db.info["user_id"])
    f = svc.create(FollowupCreate(opportunity_id=opp_id, due_date=date(2026, 11, 12)))
    assert f.done_at is None

    done = svc.update(f.id, FollowupUpdate(status=FollowupStatus.done))
    assert done.done_at == clock.now()

    reopened = svc.update(f.id, FollowupUpdate(status=FollowupStatus.pending))
    assert reopened.done_at is None


def test_followup_snooze_changes_due_date_only(db: Session, clock: Clock, opp_id: int) -> None:
    svc = FollowupService(db, clock, db.info["user_id"])
    f = svc.create(FollowupCreate(opportunity_id=opp_id, due_date=date(2026, 11, 12)))
    snoozed = svc.update(f.id, FollowupUpdate(due_date=date(2026, 11, 16)))
    assert snoozed.due_date == date(2026, 11, 16)
    assert snoozed.status == FollowupStatus.pending


def test_followup_list_filters_by_status_and_due(db: Session, clock: Clock, opp_id: int) -> None:
    svc = FollowupService(db, clock, db.info["user_id"])
    early = svc.create(FollowupCreate(opportunity_id=opp_id, due_date=date(2026, 11, 10)))
    svc.create(FollowupCreate(opportunity_id=opp_id, due_date=date(2026, 11, 20)))
    svc.update(early.id, FollowupUpdate(status=FollowupStatus.done))

    pending_due = svc.list(status=FollowupStatus.pending, due_on_or_before=date(2026, 11, 15))
    assert pending_due == []
    assert len(svc.list(due_on_or_before=date(2026, 11, 15))) == 1


def test_followup_requires_existing_opportunity(db: Session, clock: Clock) -> None:
    with pytest.raises(NotFoundError):
        FollowupService(db, clock, db.info["user_id"]).create(
            FollowupCreate(opportunity_id=999_999, due_date=date(2026, 11, 12))
        )


def test_interaction_defaults_occurred_at_to_now(db: Session, clock: Clock, opp_id: int) -> None:
    i = InteractionService(db, clock, db.info["user_id"]).create(
        InteractionCreate(opportunity_id=opp_id, type=InteractionType.call)
    )
    assert i.occurred_at == clock.now()


def test_interaction_requires_existing_opportunity_and_contact(
    db: Session, clock: Clock, opp_id: int
) -> None:
    svc = InteractionService(db, clock, db.info["user_id"])
    with pytest.raises(NotFoundError):
        svc.create(InteractionCreate(opportunity_id=999_999, type=InteractionType.call))
    with pytest.raises(NotFoundError):
        svc.create(
            InteractionCreate(opportunity_id=opp_id, contact_id=999_999, type=InteractionType.call)
        )


def test_deleting_contact_keeps_interaction(db: Session, clock: Clock, opp_id: int) -> None:
    contacts = ContactService(db, db.info["user_id"])
    interactions = InteractionService(db, clock, db.info["user_id"])
    c = contacts.create(ContactCreate(name="Asha", opportunity_id=opp_id))
    i = interactions.create(
        InteractionCreate(opportunity_id=opp_id, contact_id=c.id, type=InteractionType.email)
    )
    contacts.delete(c.id)
    db.refresh(i)
    assert i.contact_id is None


def test_contact_search_and_opportunity_link(db: Session, opp_id: int) -> None:
    svc = ContactService(db, db.info["user_id"])
    svc.create(ContactCreate(name="Asha Rao", company="Acme", opportunity_id=opp_id))
    svc.create(ContactCreate(name="Ben Cole", company="Globex"))
    assert [c.name for c in svc.list(q="acme")] == ["Asha Rao"]
    assert [c.name for c in svc.list(opportunity_id=opp_id)] == ["Asha Rao"]


def test_contact_update_rejects_unknown_opportunity(db: Session) -> None:
    svc = ContactService(db, db.info["user_id"])
    c = svc.create(ContactCreate(name="Asha"))
    with pytest.raises(NotFoundError):
        svc.update(c.id, ContactUpdate(opportunity_id=999_999))
