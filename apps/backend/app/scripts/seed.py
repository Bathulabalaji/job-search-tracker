"""Seed sample data: `uv run python -m app.scripts.seed [--reset]`.

Goes through the services (not raw inserts) so the auto-rules run exactly as they do in the API.
Sample data only: fictional companies and people, no real IDs or credentials.
"""

import argparse
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.enums import (
    ContactRole,
    Direction,
    FollowupChannel,
    InteractionType,
    Source,
    Stage,
    WorkMode,
)
from app.models.opportunity import Opportunity
from app.schemas.contact import ContactCreate
from app.schemas.followup import FollowupCreate
from app.schemas.interaction import InteractionCreate
from app.schemas.opportunity import MoveRequest, OpportunityCreate
from app.services.contact import ContactService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService

TABLES = "followups, interactions, contacts, opportunities"


def seed(session: Session, settings: Settings) -> None:
    clock = Clock(tz=ZoneInfo(settings.timezone))
    opportunities = OpportunityService(session, clock, settings)
    contacts = ContactService(session)
    interactions = InteractionService(session, clock)
    followups = FollowupService(session, clock)
    now = clock.now()
    today = clock.today()

    def opp(**kwargs: object) -> int:
        return opportunities.create(OpportunityCreate.model_validate(kwargs)).id

    def log(
        opp_id: int,
        kind: InteractionType,
        days_ago: int,
        summary: str,
        direction: Direction = Direction.out,
        contact_id: int | None = None,
    ) -> None:
        interactions.create(
            InteractionCreate(
                opportunity_id=opp_id,
                contact_id=contact_id,
                type=kind,
                direction=direction,
                summary=summary,
                occurred_at=now - timedelta(days=days_ago),
            )
        )

    # Found: not applied yet.
    opp(
        company="Northwind Labs",
        role="Backend Engineer (Python)",
        source=Source.linkedin,
        stack_tags=["python", "fastapi", "postgresql"],
        location="Bengaluru",
        work_mode=WorkMode.hybrid,
        priority=1,
        fit_score=86,
        next_action="Tailor resume and apply",
        next_action_due=today + timedelta(days=1),
    )
    opp(
        company="Contoso Systems",
        role="Python Developer",
        source=Source.naukri,
        stack_tags=["python", "django"],
        location="Hyderabad",
        work_mode=WorkMode.onsite,
        priority=3,
        fit_score=55,
    )

    # Applied: auto follow-up created by the service.
    applied = opp(
        company="Globex Technologies",
        role="Full-Stack Engineer",
        source=Source.referral,
        stack_tags=["react", "typescript", "fastapi"],
        location="Remote (India)",
        work_mode=WorkMode.remote,
        priority=1,
        fit_score=90,
        stage=Stage.applied,
        expected_ctc_note="Discuss after first round",
    )
    log(applied, InteractionType.email, 1, "Sent application with referral note")

    # Applied long ago and silent: should show a ghosted suggestion.
    quiet = opp(
        company="Initech",
        role="Software Engineer II",
        source=Source.naukri,
        stack_tags=["python", "aws"],
        location="Pune",
        work_mode=WorkMode.hybrid,
        priority=2,
        fit_score=70,
        stage=Stage.applied,
    )
    log(quiet, InteractionType.email, 26, "Applied through portal")

    # Screening, with a recruiter contact and an overdue follow-up.
    screening = opp(
        company="Umbrella Analytics",
        role="Data Platform Engineer",
        source=Source.recruiter,
        stack_tags=["python", "sql", "airflow"],
        location="Chennai",
        work_mode=WorkMode.hybrid,
        priority=2,
        fit_score=78,
        stage=Stage.screening,
    )
    recruiter = contacts.create(
        ContactCreate(
            name="Priya Nair",
            role=ContactRole.recruiter,
            company="Umbrella Analytics",
            email="priya.nair@example.com",
            opportunity_id=screening,
            notes="Prefers WhatsApp after 6pm",
        )
    )
    log(
        screening,
        InteractionType.call,
        4,
        "Intro call, role and notice period",
        Direction.in_,
        recruiter.id,
    )
    followups.create(
        FollowupCreate(
            opportunity_id=screening,
            due_date=today - timedelta(days=2),
            channel=FollowupChannel.whatsapp,
            message_draft="Hi Priya, checking in on next steps for the Data Platform role.",
        )
    )

    # Interview scheduled / interviewing.
    scheduled = opp(
        company="Stark Industries India",
        role="Senior Backend Engineer",
        source=Source.referral,
        stack_tags=["python", "fastapi", "kafka"],
        location="Bengaluru",
        work_mode=WorkMode.hybrid,
        priority=1,
        fit_score=92,
        stage=Stage.found,
    )
    opportunities.move(scheduled, MoveRequest(stage=Stage.applied))
    opportunities.move(scheduled, MoveRequest(stage=Stage.screening))
    opportunities.move(
        scheduled, MoveRequest(stage=Stage.interview_scheduled, note="Technical round Friday")
    )
    manager = contacts.create(
        ContactCreate(
            name="Rahul Mehta",
            role=ContactRole.manager,
            company="Stark Industries India",
            opportunity_id=scheduled,
        )
    )
    log(scheduled, InteractionType.interview, 0, "Round 1 scheduled", Direction.in_, manager.id)

    interviewing = opp(
        company="Wayne Enterprises",
        role="Platform Engineer",
        source=Source.linkedin,
        stack_tags=["python", "kubernetes"],
        location="Remote (India)",
        work_mode=WorkMode.remote,
        priority=2,
        fit_score=74,
        stage=Stage.interviewing,
    )
    log(interviewing, InteractionType.interview, 3, "System design round done", Direction.in_)

    # Late and closed stages.
    opp(
        company="Hooli",
        role="Backend Engineer",
        source=Source.walkin,
        stage=Stage.offer,
        stack_tags=["python"],
        location="Gurugram",
        priority=1,
        fit_score=82,
        expected_ctc_note="Offer pending negotiation",
    )
    opp(
        company="Pied Piper",
        role="API Developer",
        source=Source.linkedin,
        stage=Stage.rejected,
        stack_tags=["python", "fastapi"],
        priority=3,
        fit_score=60,
    )
    opp(
        company="Vandelay Industries",
        role="Backend Developer",
        source=Source.other,
        stage=Stage.parked,
        stack_tags=["python"],
        priority=3,
    )

    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample data.")
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing opportunity data first."
    )
    args = parser.parse_args()
    settings = get_settings()

    with SessionLocal() as session:
        existing = session.scalar(select(func.count()).select_from(Opportunity)) or 0
        if existing and not args.reset:
            raise SystemExit(
                f"{existing} opportunities already exist. Re-run with --reset to wipe and reseed."
            )
        if args.reset:
            if settings.environment != "local":
                raise SystemExit("--reset is only allowed when ENVIRONMENT=local.")
            session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        seed(session, settings)
    print("Seeded sample data.")


if __name__ == "__main__":
    main()
