from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.emails.mailer import AuthMailer
from app.emails.sender import SuppressedSender
from app.models.opportunity import Opportunity
from app.services.auth import AuthService
from app.services.google_auth import GoogleIdTokenVerifier
from tests.auth_helpers import make_user


def _service(db: Session, clock: Clock, settings: Settings) -> AuthService:
    return AuthService(
        db, clock, settings, AuthMailer(SuppressedSender(), settings), GoogleIdTokenVerifier("")
    )


def _add_legacy_row(db: Session) -> Opportunity:
    row = Opportunity(company="Legacy Co", role="Old row")  # no owner: predates accounts
    db.add(row)
    db.flush()
    return row


def test_rows_without_an_owner_are_invisible_to_everyone(db: Session) -> None:
    from app.repositories.opportunity import OpportunityRepository

    row = _add_legacy_row(db)
    assert OpportunityRepository(db, db.info["user_id"]).get(row.id) is None


def test_the_first_account_to_verify_claims_legacy_data(
    db: Session, clock: Clock, settings: Settings
) -> None:
    row = _add_legacy_row(db)
    user = make_user(db, "first@example.com", verified=False)

    _service(db, clock, settings)._mark_verified(user)  # noqa: SLF001

    db.refresh(row)
    assert row.user_id == user.id


def test_claiming_happens_once_later_accounts_get_nothing(
    db: Session, clock: Clock, settings: Settings
) -> None:
    row = _add_legacy_row(db)
    first = make_user(db, "first@example.com", verified=False)
    second = make_user(db, "second@example.com", verified=False, name="Second Person")
    service = _service(db, clock, settings)

    service._mark_verified(first)  # noqa: SLF001
    service._mark_verified(second)  # noqa: SLF001

    db.refresh(row)
    assert row.user_id == first.id


def test_with_an_owner_email_configured_only_that_account_can_claim(
    db: Session, clock: Clock, settings: Settings
) -> None:
    configured = settings.model_copy(update={"legacy_data_owner_email": "Owner@Example.com"})
    row = _add_legacy_row(db)
    stranger = make_user(db, "stranger@example.com", verified=False, name="Stray Nger")
    owner = make_user(db, "owner@example.com", verified=False, name="The Owner")
    service = _service(db, clock, configured)

    service._mark_verified(stranger)  # noqa: SLF001
    db.refresh(row)
    assert row.user_id is None  # a stranger who verifies first gets nothing

    service._mark_verified(owner)  # noqa: SLF001
    db.refresh(row)
    assert row.user_id == owner.id


def test_the_claim_covers_every_per_user_table(
    db: Session, clock: Clock, settings: Settings
) -> None:
    from app.services.legacy import OWNED_MODELS

    tables = {m.__tablename__ for m in OWNED_MODELS}
    assert tables == {
        "opportunities", "contacts", "interactions", "followups",
        "daily_logs", "weekly_targets", "prep_items", "resumes",
    }  # fmt: skip
    in_db = {
        r[0]
        for r in db.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE column_name = 'user_id' AND table_schema = 'public'"
            )
        )
    }
    # every table with a user_id column (except the auth tables, which own it differently)
    assert tables <= in_db
    # Auth tables are looked up by secret, provider usage events are operational logs, and
    # chat rows only ever exist with an owner (the assistant postdates accounts): none of
    # them can hold unclaimed legacy data.
    assert in_db - tables == {
        "auth_identities",
        "auth_tokens",
        "sessions",
        "provider_usage_events",
        "chat_conversations",
        "chat_messages",
        "chat_runs",
    }


def test_all_owned_rows_are_found_by_a_claim(db: Session, clock: Clock, settings: Settings) -> None:
    from datetime import date

    from app.models.daily_log import DailyLog

    log = DailyLog(log_date=date(2026, 11, 10))
    db.add(log)
    db.flush()
    user = make_user(db, "first@example.com", verified=False)
    _service(db, clock, settings)._mark_verified(user)  # noqa: SLF001
    assert db.scalar(select(DailyLog.user_id).where(DailyLog.id == log.id)) == user.id


def test_a_deployed_site_never_auto_claims_without_an_owner_email(
    db: Session, clock: Clock, settings: Settings
) -> None:
    """On a real domain, 'first to sign up wins' would hand your data to a stranger."""
    deployed = settings.model_copy(update={"frontend_url": "https://tracker.example.com"})
    row = _add_legacy_row(db)
    stranger = make_user(db, "stranger@example.com", verified=False, name="Stray Nger")

    _service(db, clock, deployed)._mark_verified(stranger)  # noqa: SLF001

    db.refresh(row)
    assert row.user_id is None


def test_a_deployed_site_claims_for_the_configured_owner(
    db: Session, clock: Clock, settings: Settings
) -> None:
    deployed = settings.model_copy(
        update={
            "frontend_url": "https://tracker.example.com",
            "legacy_data_owner_email": "owner@example.com",
        }
    )
    row = _add_legacy_row(db)
    owner = make_user(db, "owner@example.com", verified=False, name="The Owner")

    _service(db, clock, deployed)._mark_verified(owner)  # noqa: SLF001

    db.refresh(row)
    assert row.user_id == owner.id
