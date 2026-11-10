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
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.daily_log import DailyLog
from app.models.enums import (
    ContactRole,
    Direction,
    FollowupChannel,
    InteractionType,
    PrepCategory,
    PrepStatus,
    Source,
    Stage,
    WorkMode,
)
from app.models.opportunity import Opportunity
from app.models.prep_item import PrepItem
from app.models.resume import Resume
from app.models.weekly_target import WeeklyTarget
from app.schemas.contact import ContactCreate
from app.schemas.daily_log import DailyLogCreate
from app.schemas.followup import FollowupCreate
from app.schemas.interaction import InteractionCreate
from app.schemas.opportunity import MoveRequest, OpportunityCreate
from app.schemas.prep_item import PrepItemCreate
from app.schemas.resume import ResumeCreate
from app.schemas.weekly_target import WeeklyTargetCreate
from app.services.analytics_math import week_start
from app.services.contact import ContactService
from app.services.daily_log import DailyLogService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService
from app.services.prep_item import PrepItemService
from app.services.resume import ResumeService
from app.services.weekly_target import WeeklyTargetService

TABLES = "followups, interactions, contacts, opportunities, daily_logs, weekly_targets, prep_items"


def seed_opportunities(session: Session, settings: Settings) -> None:
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
    )
    for stage in (Stage.applied, Stage.screening, Stage.interviewing):
        opportunities.move(interviewing, MoveRequest(stage=stage))
    log(interviewing, InteractionType.interview, 3, "System design round done", Direction.in_)

    # Late and closed stages, reached through real moves so funnel history exists.
    offer = opp(
        company="Hooli",
        role="Backend Engineer",
        source=Source.walkin,
        stack_tags=["python"],
        location="Gurugram",
        priority=1,
        fit_score=82,
        expected_ctc_note="Offer pending negotiation",
    )
    for stage in (Stage.applied, Stage.screening, Stage.interviewing, Stage.offer):
        opportunities.move(offer, MoveRequest(stage=stage))
    log(offer, InteractionType.email, 2, "Offer letter received", Direction.in_)

    rejected = opp(
        company="Pied Piper",
        role="API Developer",
        source=Source.linkedin,
        stack_tags=["python", "fastapi"],
        priority=3,
        fit_score=60,
    )
    for stage in (Stage.applied, Stage.screening, Stage.rejected):
        opportunities.move(rejected, MoveRequest(stage=stage))
    log(rejected, InteractionType.call, 9, "Screening call", Direction.in_)

    opp(
        company="Vandelay Industries",
        role="Backend Developer",
        source=Source.other,
        stage=Stage.parked,
        stack_tags=["python"],
        priority=3,
    )

    session.commit()


# (applications, messages, referrals, problems, mocks, hours) for the last 21 days, oldest first.
# Zero rows are rest days: they appear in the log but do not extend the streak.
ACTIVITY: list[tuple[int, int, int, int, int, float]] = [
    (2, 6, 0, 3, 0, 1.5),
    (3, 8, 1, 4, 1, 2.0),
    (0, 0, 0, 0, 0, 0.0),
    (4, 10, 1, 2, 0, 2.5),
    (1, 5, 0, 5, 1, 1.5),
    (0, 3, 0, 0, 0, 0.5),
    (0, 0, 0, 0, 0, 0.0),
    (5, 12, 2, 3, 0, 3.0),
    (3, 9, 1, 4, 1, 2.0),
    (4, 7, 0, 6, 0, 2.5),
    (2, 11, 1, 2, 1, 2.0),
    (6, 14, 2, 5, 0, 3.5),
    (1, 4, 0, 3, 0, 1.0),
    (0, 2, 0, 0, 0, 0.0),
    (3, 8, 1, 4, 1, 2.5),
    (4, 9, 1, 5, 0, 2.5),
    (2, 10, 0, 3, 1, 2.0),
    (5, 13, 2, 6, 0, 3.0),
    (3, 7, 1, 4, 1, 2.5),
    (4, 12, 1, 5, 0, 3.0),
    (2, 6, 0, 3, 0, 1.5),
]

PREP: list[tuple[str, PrepCategory, PrepStatus, int]] = [
    ("Type hints, generics and Protocols", PrepCategory.python, PrepStatus.done, 4),
    ("asyncio: tasks, gather, cancellation", PrepCategory.python, PrepStatus.doing, 3),
    ("Decorators and context managers", PrepCategory.python, PrepStatus.done, 5),
    ("Dependency injection with Depends", PrepCategory.fastapi, PrepStatus.done, 4),
    ("Background tasks and lifespan events", PrepCategory.fastapi, PrepStatus.todo, 2),
    ("Pydantic v2 validators and serialization", PrepCategory.fastapi, PrepStatus.doing, 3),
    ("Indexes and EXPLAIN ANALYZE", PrepCategory.db, PrepStatus.doing, 3),
    ("Transactions and isolation levels", PrepCategory.db, PrepStatus.todo, 2),
    ("Window functions and CTEs", PrepCategory.db, PrepStatus.done, 4),
    ("TanStack Query caching and optimistic updates", PrepCategory.react, PrepStatus.done, 4),
    ("Rendering performance and memoisation", PrepCategory.react, PrepStatus.todo, 2),
    ("Prompting and tool use with the Claude API", PrepCategory.ai, PrepStatus.doing, 3),
    ("RAG: chunking, embeddings, evaluation", PrepCategory.ai, PrepStatus.todo, 1),
    ("Design a URL shortener", PrepCategory.system_design, PrepStatus.done, 4),
    ("Design a rate limiter", PrepCategory.system_design, PrepStatus.todo, 2),
    ("Tell me about a conflict with a teammate", PrepCategory.behavioral, PrepStatus.doing, 3),
    ("Why are you leaving your current role?", PrepCategory.behavioral, PrepStatus.done, 5),
]


RESUMES: list[tuple[str, str, str, str, str | None]] = [
    (
        "Backend (Python)",
        "FastAPI, PostgreSQL, system design",
        "resume_backend_v3.pdf",
        "3",
        "Default for backend roles. Leads with the API work.",
    ),
    (
        "Full-stack",
        "React, TypeScript, FastAPI",
        "resume_fullstack_v2.pdf",
        "2",
        "Use for roles that mention React.",
    ),
    ("Data platform", "Airflow, SQL, pipelines", "resume_data_v1.pdf", "1", None),
]


def seed_resumes(session: Session) -> None:
    service = ResumeService(session)
    for label, focus, file_name, version, notes in RESUMES:
        service.create(
            ResumeCreate(
                label=label, focus=focus, file_name=file_name, version=version, notes=notes
            )
        )


def seed_activity(session: Session, settings: Settings) -> None:
    clock = Clock(tz=ZoneInfo(settings.timezone))
    today = clock.today()
    logs = DailyLogService(session, clock)
    for index, (apps, msgs, refs, problems, mocks, hours) in enumerate(ACTIVITY):
        day = today - timedelta(days=len(ACTIVITY) - 1 - index)
        logs.create(
            DailyLogCreate(
                log_date=day,
                applications_sent=apps,
                messages_sent=msgs,
                referrals_requested=refs,
                problems_solved=problems,
                mocks_done=mocks,
                hours_prep=hours,
            )
        )
    targets = WeeklyTargetService(session)
    targets.create(
        WeeklyTargetCreate(
            week_start=week_start(today),
            applications=20,
            messages=50,
            referrals=5,
            problems=25,
            mocks=3,
            interviews=3,
        )
    )


def seed_prep(session: Session) -> None:
    items = PrepItemService(session)
    for topic, category, status, confidence in PREP:
        items.create(
            PrepItemCreate(topic=topic, category=category, status=status, confidence=confidence)
        )


def _count(session: Session, model: type[Base]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample data.")
    parser.add_argument("--reset", action="store_true", help="Delete ALL existing data first.")
    args = parser.parse_args()
    settings = get_settings()

    with SessionLocal() as session:
        if args.reset:
            if settings.environment != "local":
                raise SystemExit("--reset is only allowed when ENVIRONMENT=local.")
            session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
            session.commit()

        # Each section seeds only if its own tables are empty, so re-running is safe.
        if _count(session, Opportunity) == 0:
            seed_opportunities(session, settings)
            print("Seeded opportunities, contacts, interactions and follow-ups.")
        else:
            print("Skipped opportunities (already present; use --reset to start over).")

        if _count(session, DailyLog) == 0 and _count(session, WeeklyTarget) == 0:
            seed_activity(session, settings)
            print("Seeded 21 days of daily logs and this week's targets.")
        else:
            print("Skipped daily logs and targets (already present).")

        if _count(session, PrepItem) == 0:
            seed_prep(session)
            print("Seeded prep items.")
        else:
            print("Skipped prep items (already present).")

        if _count(session, Resume) == 0:
            seed_resumes(session)
            print("Seeded resumes.")
        else:
            print("Skipped resumes (already present).")


if __name__ == "__main__":
    main()
