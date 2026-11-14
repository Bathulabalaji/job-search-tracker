"""Read-only tools over the user's data.

Each tool wraps an existing service built for the signed-in user, so scoping and business
rules are the services' own; the model never supplies a user id. Results are compacted
(short keys, capped lists and text) because on free tiers prompt tokens are the scarce thing.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway
from app.models.enums import FollowupStatus, PrepCategory, PrepStatus, Source, Stage
from app.repositories.resume_chunk import ResumeChunkRepository
from app.services.analytics import AnalyticsService
from app.services.contact import ContactService
from app.services.dashboard import DashboardService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService
from app.services.prep_item import PrepItemService
from app.services.resume import ResumeService

MAX_RESULT_CHARS = 1_400
MAX_TEXT = 300
QUERY_CANCELLED = "57014"  # Postgres: statement_timeout hit


class ToolTimeout(Exception):
    """A lookup took longer than the database was allowed to spend on it."""


def with_statement_timeout(
    session: Session, seconds: float, fn: Callable[[BaseModel], dict[str, Any]]
) -> Callable[[BaseModel], dict[str, Any]]:
    """Bound a tool's database time with Postgres' own `statement_timeout`.

    Set per transaction (`SET LOCAL`), so it never leaks into other requests; a cancelled
    query aborts the transaction, which is rolled back so the run can carry on.
    """
    ms = max(1, int(seconds * 1000))

    def run(args: BaseModel) -> dict[str, Any]:
        session.execute(text(f"SET LOCAL statement_timeout = {ms}"))
        db_failed = False
        try:
            return fn(args)
        except OperationalError as exc:
            db_failed = True
            session.rollback()
            if getattr(exc.orig, "sqlstate", None) == QUERY_CANCELLED or (
                "statement timeout" in str(exc).lower()
            ):
                raise ToolTimeout(f"lookup exceeded {seconds:g}s") from exc
            raise
        finally:
            if not db_failed:
                try:
                    session.execute(text("SET LOCAL statement_timeout = DEFAULT"))
                except Exception:  # the transaction is aborted by another DB error
                    session.rollback()

    return run


def _clip(text: str | None, limit: int = MAX_TEXT) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _d(value: date | None) -> str | None:
    return value.isoformat() if value else None


def compact(value: object) -> str:
    """JSON for the prompt, cut at MAX_RESULT_CHARS with an explicit marker."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[: MAX_RESULT_CHARS - 40] + '…"(truncated: ask for fewer rows)"'


# ---- argument schemas (these become the JSON schemas the model sees) -------------------------


class NoArgs(BaseModel):
    pass


class ListOpportunitiesArgs(BaseModel):
    stage: Stage | None = Field(None, description="Only this stage")
    priority: int | None = Field(None, ge=1, le=3, description="1 = high, 3 = low")
    source: Source | None = None
    q: str | None = Field(None, description="Text search in company or role")
    quiet_for_days: int | None = Field(
        None, ge=1, description="Only opportunities with no contact for at least this many days"
    )
    open_only: bool = Field(
        False, description="Exclude closed stages (accepted, rejected, ghosted, parked)"
    )
    limit: int = Field(10, ge=1, le=10)


class OpportunityIdArgs(BaseModel):
    opportunity_id: int


class ListFollowupsArgs(BaseModel):
    status: FollowupStatus | None = Field(FollowupStatus.pending)
    due_on_or_before: date | None = None
    opportunity_id: int | None = None


class WeeklyArgs(BaseModel):
    week_of: date | None = Field(None, description="Any date in the week; default this week")


class ListContactsArgs(BaseModel):
    q: str | None = Field(None, description="Text search in name, company or notes")
    opportunity_id: int | None = None


class ListPrepArgs(BaseModel):
    category: PrepCategory | None = None
    status: PrepStatus | None = None


class ResumeIdArgs(BaseModel):
    resume_id: int


class SearchResumeArgs(BaseModel):
    query: str = Field(min_length=2, max_length=300, description="What to look for")
    resume_id: int | None = Field(None, description="Only this resume; default all")


CLOSED_STAGES = {Stage.accepted, Stage.rejected, Stage.ghosted, Stage.parked}


@dataclass(frozen=True)
class AssistantTool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[BaseModel], dict[str, Any]]
    summarize: Callable[[dict[str, Any]], str]

    def as_langchain(self) -> StructuredTool:
        def _never_called(**_: Any) -> str:  # the graph executes tools itself
            raise RuntimeError("assistant tools are executed by the graph")

        return StructuredTool.from_function(
            func=_never_called,
            name=self.name,
            description=self.description,
            args_schema=self.args,
        )


def _rows(n: int, noun: str) -> str:
    if n == 1:
        return f"1 {noun}"
    plural = noun[:-1] + "ies" if noun.endswith("y") else noun + "s"
    return f"{n} {plural}"


def build_read_tools(
    session: Session,
    clock: Clock,
    settings: Settings,
    user_id: int,
    *,
    timeout_seconds: float | None = None,
    gateway: LLMGateway | None = None,
) -> dict[str, AssistantTool]:
    opportunities = OpportunityService(session, clock, settings, user_id)
    dashboard = DashboardService(session, clock, user_id)
    followups = FollowupService(session, clock, user_id)
    interactions = InteractionService(session, clock, user_id)
    analytics = AnalyticsService(session, clock, user_id)
    contacts = ContactService(session, user_id)
    prep = PrepItemService(session, user_id)
    resumes = ResumeService(session, user_id)
    chunks = ResumeChunkRepository(session, user_id)

    def get_today(_: BaseModel) -> dict[str, Any]:
        today = dashboard.today()
        return {
            "today": _d(today.today),
            "followups": [
                {
                    "id": f.id,
                    "opp": f.opportunity_id,
                    "company": f.company,
                    "role": f.role,
                    "due": _d(f.due_date),
                    "days_overdue": f.days_overdue,
                    "channel": f.channel,
                }
                for f in today.followups[:10]
            ],
            "interviews": [
                {
                    "opp": i.opportunity_id,
                    "company": i.company,
                    "role": i.role,
                    "at": i.occurred_at.astimezone(clock.tz).strftime("%Y-%m-%d %H:%M"),
                    "summary": _clip(i.summary, 120),
                }
                for i in today.interviews[:10]
            ],
            "next_actions": [
                {
                    "opp": a.opportunity_id,
                    "company": a.company,
                    "role": a.role,
                    "stage": a.stage,
                    "action": _clip(a.next_action, 120),
                    "due": _d(a.next_action_due),
                    "overdue": a.overdue,
                }
                for a in today.next_actions[:10]
            ],
        }

    def get_pipeline_summary(_: BaseModel) -> dict[str, Any]:
        s = dashboard.summary()
        return {
            "per_stage": {k.value: v for k, v in s.counts_per_stage.items() if v},
            "total": s.total,
            "applied_total": s.applied_total,
            "responded_total": s.responded_total,
            "response_rate": s.response_rate,
            "interviews_this_week": s.interviews_this_week,
        }

    def list_opportunities(raw: BaseModel) -> dict[str, Any]:
        a = ListOpportunitiesArgs.model_validate(raw.model_dump())
        rows = opportunities.list(
            stage=a.stage, priority=a.priority, source=a.source, q=a.q, limit=200
        )
        if a.open_only:
            rows = [r for r in rows if r.stage not in CLOSED_STAGES]
        if a.quiet_for_days is not None:
            quiet = a.quiet_for_days
            rows = [r for r in rows if r.days_since_contact >= quiet]
            rows.sort(key=lambda r: r.days_since_contact, reverse=True)
        items = [
            {
                "id": r.id,
                "company": r.company,
                "role": r.role,
                "stage": r.stage,
                "priority": r.priority,
                "days_since_contact": r.days_since_contact,
                "ghost_suggested": r.ghosted_suggestion or None,
                "next_action": _clip(r.next_action, 80),
                "next_due": _d(r.next_action_due),
            }
            for r in rows[: a.limit]
        ]
        return {"items": items, "total_matching": len(rows)}

    def get_opportunity(raw: BaseModel) -> dict[str, Any]:
        a = OpportunityIdArgs.model_validate(raw.model_dump())
        o = opportunities.get(a.opportunity_id)
        recent = interactions.list(opportunity_id=o.id, limit=5)
        pending = followups.list(opportunity_id=o.id, status=FollowupStatus.pending, limit=5)
        people = contacts.list(opportunity_id=o.id, limit=5)
        return {
            "id": o.id,
            "company": o.company,
            "role": o.role,
            "stage": o.stage,
            "source": o.source,
            "priority": o.priority,
            "fit_score": o.fit_score,
            "location": o.location,
            "work_mode": o.work_mode,
            "stack": o.stack_tags[:10],
            "next_action": _clip(o.next_action, 150),
            "next_due": _d(o.next_action_due),
            "days_since_contact": o.days_since_contact,
            "jd": _clip(o.jd_text, 500),
            "ctc_note": _clip(o.expected_ctc_note, 120),
            "recent_interactions": [
                {
                    "type": i.type,
                    "dir": i.direction,
                    "on": _d(i.occurred_at.date()),
                    "summary": _clip(i.summary, 120),
                }
                for i in recent
            ],
            "pending_followups": [
                {"id": f.id, "due": _d(f.due_date), "channel": f.channel} for f in pending
            ],
            "contacts": [{"name": c.name, "role": c.role} for c in people],
        }

    def list_followups(raw: BaseModel) -> dict[str, Any]:
        a = ListFollowupsArgs.model_validate(raw.model_dump())
        rows = followups.list(
            status=a.status,
            due_on_or_before=a.due_on_or_before,
            opportunity_id=a.opportunity_id,
            limit=15,
        )
        names = {o.id: f"{o.company} — {o.role}" for o in opportunities.list(limit=200)}
        return {
            "items": [
                {
                    "id": f.id,
                    "opp": f.opportunity_id,
                    "name": names.get(f.opportunity_id),
                    "due": _d(f.due_date),
                    "channel": f.channel,
                    "status": f.status,
                    "draft": _clip(f.message_draft, 100),
                }
                for f in rows
            ]
        }

    def get_weekly_analytics(raw: BaseModel) -> dict[str, Any]:
        a = WeeklyArgs.model_validate(raw.model_dump())
        w = analytics.weekly(a.week_of)
        return {
            "week": f"{_d(w.week_start)}..{_d(w.week_end)}",
            "progress": [
                {"metric": p.metric, "actual": p.actual, "target": p.target} for p in w.progress
            ],
            "hours_prep": w.totals.hours_prep,
            "funnel": [{"step": f.label, "count": f.count} for f in w.funnel],
            "by_source": [
                {"source": s.source, "applied": s.applied, "response_rate": s.response_rate}
                for s in w.response_by_source
                if s.applied
            ],
            "scorecard": w.scorecard.model_dump(),
        }

    def list_contacts(raw: BaseModel) -> dict[str, Any]:
        a = ListContactsArgs.model_validate(raw.model_dump())
        rows = contacts.list(q=a.q, opportunity_id=a.opportunity_id, limit=10)
        return {
            "items": [
                {
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "company": c.company,
                    "opp": c.opportunity_id,
                    "notes": _clip(c.notes, 100),
                }
                for c in rows
            ]
        }

    def list_prep_items(raw: BaseModel) -> dict[str, Any]:
        a = ListPrepArgs.model_validate(raw.model_dump())
        rows = prep.list(category=a.category, status=a.status, limit=25)
        return {
            "items": [
                {
                    "topic": p.topic,
                    "category": p.category,
                    "status": p.status,
                    "confidence": p.confidence,
                }
                for p in rows
            ]
        }

    def list_resumes(_: BaseModel) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": r.id,
                    "label": r.label,
                    "focus": r.focus,
                    "version": r.version,
                    "notes": _clip(r.notes, 100),
                    "file": r.file_name if r.storage_key else None,
                    "indexed": (r.embed_status == "ready") if r.storage_key else None,
                }
                for r in resumes.list(limit=20)
            ]
        }

    def get_resume_profile(raw: BaseModel) -> dict[str, Any]:
        a = ResumeIdArgs.model_validate(raw.model_dump())
        r = resumes.get(a.resume_id)
        if not r.storage_key:
            return {
                "id": r.id,
                "label": r.label,
                "profile": None,
                "note": "No file is attached to this resume yet.",
            }
        profile = r.profile or {}
        return {
            "id": r.id,
            "label": r.label,
            "focus": r.focus,
            "file": r.file_name,
            "indexed": r.embed_status == "ready",
            "profile": {
                "titles": profile.get("titles", [])[:5],
                "years_experience": profile.get("years_experience"),
                "skills": [sk.get("name") for sk in profile.get("skills", [])][:30],
                "domains": profile.get("domains", [])[:6],
                "education": profile.get("education", [])[:3],
                "summary": _clip(profile.get("summary"), 300),
            }
            if profile
            else None,
            "excerpt": _clip(r.extracted_text, 400) if not profile else None,
        }

    def search_resume(raw: BaseModel) -> dict[str, Any]:
        a = SearchResumeArgs.model_validate(raw.model_dump())
        scope = [resumes.get(a.resume_id).id] if a.resume_id is not None else None
        if gateway is not None and gateway.enabled:
            try:
                [vector] = gateway.embed([a.query], kind="query")
                hits = chunks.similar(vector, resume_ids=scope, k=5)
                return {
                    "matches": [
                        {
                            "resume_id": h.resume_id,
                            "section": h.section,
                            "score": round(h.score, 2),
                            "text": _clip(h.text, 350),
                        }
                        for h in hits
                    ],
                    "method": "semantic",
                }
            except LLMError:
                pass  # fall back to plain text search below
        words = [w for w in a.query.lower().split() if len(w) > 2][:6]
        matches: list[dict[str, Any]] = []
        for r in resumes.list(limit=20):
            if scope is not None and r.id not in scope:
                continue
            text = (r.extracted_text or "").lower()
            for word in words:
                at = text.find(word)
                if at >= 0:
                    snippet = (r.extracted_text or "")[max(0, at - 150) : at + 200]
                    matches.append(
                        {
                            "resume_id": r.id,
                            "section": "text",
                            "score": None,
                            "text": _clip(snippet),
                        }
                    )
                    break
        return {"matches": matches[:5], "method": "keyword"}

    def count(key: str, noun: str) -> Callable[[dict[str, Any]], str]:
        return lambda result: _rows(len(result.get(key, [])), noun)

    tools = [
        AssistantTool(
            "get_today",
            "Today's plan: follow-ups due or overdue, interviews today, next actions.",
            NoArgs,
            get_today,
            lambda r: (
                f"{_rows(len(r['followups']), 'follow-up')}, "
                f"{_rows(len(r['interviews']), 'interview')}"
            ),
        ),
        AssistantTool(
            "get_pipeline_summary",
            "Counts per stage, totals, response rate and interviews this week.",
            NoArgs,
            get_pipeline_summary,
            lambda r: f"{r['total']} opportunities",
        ),
        AssistantTool(
            "list_opportunities",
            "Search the pipeline. Filter by stage, priority, source, text, or how long since "
            "the last contact (quiet_for_days) to find applications that have gone quiet.",
            ListOpportunitiesArgs,
            list_opportunities,
            count("items", "opportunity"),
        ),
        AssistantTool(
            "get_opportunity",
            "Full details of one opportunity: JD excerpt, recent interactions, pending "
            "follow-ups and contacts.",
            OpportunityIdArgs,
            get_opportunity,
            lambda r: f"{r['company']} — {r['role']}",
        ),
        AssistantTool(
            "list_followups",
            "Follow-ups (default: pending), optionally due on or before a date or for one "
            "opportunity.",
            ListFollowupsArgs,
            list_followups,
            count("items", "follow-up"),
        ),
        AssistantTool(
            "get_weekly_analytics",
            "A week's activity vs targets, funnel, response rate by source and scorecard.",
            WeeklyArgs,
            get_weekly_analytics,
            lambda r: f"week {r['week']}",
        ),
        AssistantTool(
            "list_contacts",
            "Recruiters, HR, managers and referrers.",
            ListContactsArgs,
            list_contacts,
            count("items", "contact"),
        ),
        AssistantTool(
            "list_prep_items",
            "Interview-prep topics with status and confidence (1-5).",
            ListPrepArgs,
            list_prep_items,
            count("items", "topic"),
        ),
        AssistantTool(
            "list_resumes",
            "The user's resume versions (label, focus, version, attached file).",
            NoArgs,
            list_resumes,
            count("items", "resume"),
        ),
        AssistantTool(
            "get_resume_profile",
            "The extracted profile of one uploaded resume: titles, years, skills, domains.",
            ResumeIdArgs,
            get_resume_profile,
            lambda r: str(r.get("label", "resume")),
        ),
        AssistantTool(
            "search_resume",
            "Find passages in the user's uploaded resumes about a topic, skill or project.",
            SearchResumeArgs,
            search_resume,
            count("matches", "match"),
        ),
    ]
    if timeout_seconds:
        tools = [
            AssistantTool(
                t.name,
                t.description,
                t.args,
                with_statement_timeout(session, timeout_seconds, t.run),
                t.summarize,
            )
            for t in tools
        ]
    return {t.name: t for t in tools}


# Which tools each guardrail intent gets. Fewer schemas = fewer prompt tokens.
CORE = ("get_today", "get_pipeline_summary", "list_opportunities", "get_opportunity")
WRITE = (
    "move_opportunity",
    "add_followup",
    "mark_followup",
    "log_interaction",
    "set_next_action",
    "create_opportunity",
)
TOOLSETS: dict[str, tuple[str, ...]] = {
    "today": CORE + ("list_followups",) + WRITE,
    "pipeline": CORE + ("list_followups",) + WRITE,
    "followups": CORE + ("list_followups",) + WRITE,
    "write": CORE + ("list_followups", "list_contacts") + WRITE,
    "analytics": ("get_weekly_analytics", "get_pipeline_summary", "list_opportunities"),
    "contacts": ("list_contacts", "list_opportunities", "get_opportunity"),
    "prep": ("list_prep_items", "list_opportunities", "get_opportunity"),
    "resumes": (
        "list_resumes",
        "get_resume_profile",
        "search_resume",
        "list_opportunities",
        "get_opportunity",
    ),
    "smalltalk": (),
}
ALL_TOOLS = (
    "get_today",
    "get_pipeline_summary",
    "list_opportunities",
    "get_opportunity",
    "list_followups",
    "get_weekly_analytics",
    "list_contacts",
    "list_prep_items",
    "list_resumes",
    "get_resume_profile",
    "search_resume",
) + WRITE


def toolset_for(intent: str | None) -> tuple[str, ...]:
    return TOOLSETS.get(intent or "", ALL_TOOLS)
