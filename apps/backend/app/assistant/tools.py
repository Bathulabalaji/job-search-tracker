"""Read-only tools over the user's data.

Each tool wraps an existing service built for the signed-in user, so scoping and business
rules are the services' own; the model never supplies a user id. Results are compacted
(short keys, capped lists and text) because on free tiers prompt tokens are the scarce thing.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.jobsearch.sanitize import untrusted
from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway
from app.models.enums import FollowupStatus, PrepCategory, PrepStatus, Source, Stage
from app.repositories.resume_chunk import ResumeChunkRepository
from app.schemas.job import JobPostingRead, JobSearchRequest
from app.schemas.match import MatchResult
from app.schemas.messaging import PreviewRequest
from app.services.analytics import AnalyticsService
from app.services.contact import ContactService
from app.services.dashboard import DashboardService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.job_match import JobMatchService
from app.services.job_search import JobSearchService
from app.services.messaging import MessagingService
from app.services.opportunity import OpportunityService
from app.services.prep_item import PrepItemService
from app.services.recommendations import RecommendationService
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


def compact(value: object, limit: int = MAX_RESULT_CHARS) -> str:
    """JSON for the prompt, cut at `limit` characters with an explicit marker."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 40] + '…"(truncated: ask for fewer rows)"'


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


class SearchJobsArgs(BaseModel):
    query: str = Field(
        min_length=2, max_length=200, description="Role and key skills, e.g. 'backend python'"
    )
    location: str | None = Field(None, max_length=100, description="City, e.g. Bengaluru")
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    posted_within_days: int = Field(7, ge=1, le=30)
    limit: int = Field(5, ge=1, le=8)


class JobIdArgs(BaseModel):
    job_posting_id: int


class WhichResumeArgs(BaseModel):
    opportunity_id: int | None = Field(None, description="An opportunity in the pipeline")
    job_posting_id: int | None = Field(None, description="A posting returned by search_jobs")

    @model_validator(mode="after")
    def _one_target(self) -> "WhichResumeArgs":
        if (self.opportunity_id is None) == (self.job_posting_id is None):
            raise ValueError("give exactly one of opportunity_id or job_posting_id")
        return self


class DraftMessageArgs(BaseModel):
    opportunity_id: int
    template_key: str | None = Field(
        None, description="A key from the suggestions (sys:follow_up_1). Omit for what is due next."
    )
    channel: Literal["email", "linkedin", "linkedin_note"] = "email"
    contact_id: int | None = None


class RecommendationsArgs(BaseModel):
    limit: int = Field(5, ge=1, le=10)


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
    # Room this tool's result may take in the prompt.
    max_chars: int = MAX_RESULT_CHARS

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
    if noun.endswith("y"):
        plural = noun[:-1] + "ies"
    elif noun.endswith(("ch", "sh", "s", "x")):
        plural = noun + "es"
    else:
        plural = noun + "s"
    return f"{n} {plural}"


def build_read_tools(
    session: Session,
    clock: Clock,
    settings: Settings,
    user_id: int,
    *,
    timeout_seconds: float | None = None,
    gateway: LLMGateway | None = None,
    jobs: JobSearchService | None = None,
    matching: JobMatchService | None = None,
    recs: RecommendationService | None = None,
    messaging: MessagingService | None = None,
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

    def job_card(job: JobPostingRead) -> dict[str, Any]:
        return {"type": "job", **job.model_dump(mode="json", exclude={"description"})}

    def search_jobs(raw: BaseModel) -> dict[str, Any]:
        assert jobs is not None
        a = SearchJobsArgs.model_validate(raw.model_dump())
        found = jobs.search(JobSearchRequest(**a.model_dump()))
        listed = [
            {
                "job_posting_id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "mode": j.work_mode,
                "site": j.source_site,
                "posted": _d(j.posted_at.date()) if j.posted_at else None,
                "still_open": {"active": "yes", "inactive": "no"}.get(j.active_status, "unknown"),
                "salary": j.salary_text,
                "already_tracked": j.tracked_opportunity_id is not None or None,
            }
            for j in found.results
        ]
        return {
            "count": len(listed),
            "from_cache": found.from_cache or None,
            "notices": [n.message for n in found.notices] or None,
            # Titles and companies come from job boards: data, never instructions.
            "postings": untrusted(json.dumps(listed, ensure_ascii=False, separators=(",", ":"))),
            "_cards": [job_card(j) for j in found.results],
        }

    def match_card(result: MatchResult) -> dict[str, Any]:
        return {"type": "match", **result.model_dump(mode="json")}

    def which_resume_fits(raw: BaseModel) -> dict[str, Any]:
        assert matching is not None
        a = WhichResumeArgs.model_validate(raw.model_dump())
        result = (
            matching.match_opportunity(a.opportunity_id)
            if a.opportunity_id is not None
            else matching.match_posting(a.job_posting_id or 0)
        )
        return {
            "job": result.target_label,
            "best_resume": next(
                (m.label for m in result.per_resume if m.resume_id == result.best_resume_id), None
            ),
            "cached": result.cached or None,
            "resumes": [
                {
                    "resume_id": m.resume_id,
                    "label": m.label,
                    "score": m.score,
                    "similarity": round(m.vector_score * 100) if m.vector_score else None,
                    "matched": m.matched_skills[:6],
                    "missing": m.missing_skills[:6],
                    "suggestions": m.suggestions[:2],
                }
                for m in result.per_resume
            ],
            "_cards": [match_card(result)],
        }

    def draft_message(raw: BaseModel) -> dict[str, Any]:
        assert messaging is not None
        a = DraftMessageArgs.model_validate(raw.model_dump())
        advice = messaging.suggestions(a.opportunity_id)
        options = [
            {
                "template_key": s.template_key,
                "title": s.title,
                "channel": s.channel,
                "why": s.reason,
                "send_now": s.due,
                "kind": s.kind,
            }
            for s in advice.suggestions[:4]
        ]
        key = a.template_key or next(
            (s.template_key for s in advice.suggestions if s.kind == "send" and s.due), None
        )
        if key is None:
            return {"suggestions": options, "note": "Nothing is due to send right now."}
        suggested = next((s for s in advice.suggestions if s.template_key == key), None)
        contact = a.contact_id or (suggested.contact_id if suggested else None)
        draft = messaging.preview(
            a.opportunity_id,
            PreviewRequest(template_key=key, channel=a.channel, contact_id=contact),
        )
        opp = opportunities.get(a.opportunity_id)
        return {
            "suggestions": options,
            "template": draft.template_name,
            "to": draft.to_name,
            "gaps": [m.label for m in draft.missing] or None,
            "warnings": draft.warnings or None,
            "_cards": [
                {
                    "type": "draft",
                    "opportunity_id": a.opportunity_id,
                    "company": opp.company,
                    "role": opp.role,
                    "template_key": key,
                    "template_name": draft.template_name,
                    "channel": draft.channel,
                    "to": draft.to,
                    "to_name": draft.to_name,
                    "subject": draft.subject,
                    "body": draft.body,
                    "missing": [m.label for m in draft.missing],
                }
            ],
        }

    def get_recommendations(raw: BaseModel) -> dict[str, Any]:
        assert recs is not None
        a = RecommendationsArgs.model_validate(raw.model_dump())
        feed = recs.feed(a.limit)
        return {
            "count": len(feed),
            "jobs": [
                {
                    "job_posting_id": r.job.id,
                    "title": r.job.title,
                    "company": r.job.company,
                    "location": r.job.location,
                    "similarity": round(r.vector_score * 100),
                    "best_resume": r.best_resume_label,
                }
                for r in feed
            ],
            "_cards": [job_card(r.job) for r in feed],
        }

    def refresh_recommendations(_: BaseModel) -> dict[str, Any]:
        assert recs is not None
        done = recs.refresh()
        return {
            "new": done.added,
            "considered": done.considered,
            "notices": [n.message for n in done.notices] or None,
        }

    def check_job_active(raw: BaseModel) -> dict[str, Any]:
        assert jobs is not None
        a = JobIdArgs.model_validate(raw.model_dump())
        job = jobs.check(a.job_posting_id)
        return {
            "job_posting_id": job.id,
            "still_open": {"active": "yes", "inactive": "no"}.get(job.active_status, "unknown"),
            "_cards": [job_card(job)],
        }

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
    if jobs is not None and jobs.enabled:
        tools += [
            AssistantTool(
                "search_jobs",
                "Search live job postings (LinkedIn, Naukri, company career pages and job "
                "boards, through search APIs). The user sees each result as a card with a "
                "Track button, so do not repeat links.",
                SearchJobsArgs,
                search_jobs,
                lambda r: _rows(int(r.get("count", 0)), "job"),
                max_chars=2_600,
            ),
            AssistantTool(
                "check_job_active",
                "Check again whether a job posting from search_jobs is still open.",
                JobIdArgs,
                check_job_active,
                lambda r: f"still open: {r['still_open']}",
            ),
        ]
    if messaging is not None:
        tools.append(
            AssistantTool(
                "draft_message",
                "Draft a follow-up or outreach email or LinkedIn message for an opportunity, "
                "filled from the opportunity, its contact and the user's profile. With no "
                "template_key it picks what is due next. The user sees the draft as a card and "
                "sends it themselves; you cannot send anything. Do not paste the draft again.",
                DraftMessageArgs,
                draft_message,
                lambda r: str(r.get("template") or "nothing due"),
                max_chars=1_800,
            )
        )
    if matching is not None and gateway is not None and gateway.enabled:
        tools.append(
            AssistantTool(
                "which_resume_fits",
                "Score how well each of the user's uploaded resumes fits one job (a pipeline "
                "opportunity or a posting from search_jobs): a 0-100 score per resume, the "
                "best resume, matched and missing skills and up to 3 suggestions. Costs a "
                "model call unless nothing changed, so don't repeat it for the same job.",
                WhichResumeArgs,
                which_resume_fits,
                lambda r: f"best: {r.get('best_resume') or 'none'}",
                max_chars=2_200,
            )
        )
    if recs is not None and jobs is not None and jobs.enabled:
        tools += [
            AssistantTool(
                "get_recommendations",
                "The user's 'Jobs for you' feed: postings ranked by similarity to their "
                "resumes. Shown as cards.",
                RecommendationsArgs,
                get_recommendations,
                lambda r: _rows(int(r.get("count", 0)), "job"),
                max_chars=1_800,
            ),
            AssistantTool(
                "refresh_recommendations",
                "Look for new jobs for the user from their search profile (spends search "
                "quota; limited per day). Call get_recommendations afterwards.",
                NoArgs,
                refresh_recommendations,
                lambda r: f"{r['new']} new",
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
                t.max_chars,
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
    "set_fit_score",
)
FITS = ("which_resume_fits", "get_recommendations", "refresh_recommendations")
OUTREACH = ("draft_message",)
JOBS = ("search_jobs", "check_job_active", "add_job_to_pipeline")
TOOLSETS: dict[str, tuple[str, ...]] = {
    "today": CORE + ("list_followups",) + WRITE,
    "pipeline": CORE + ("list_followups",) + WRITE + OUTREACH,
    "followups": CORE + ("list_followups", "list_contacts") + WRITE + OUTREACH,
    "write": CORE + ("list_followups", "list_contacts") + WRITE,
    "analytics": ("get_weekly_analytics", "get_pipeline_summary", "list_opportunities"),
    "contacts": ("list_contacts", "list_opportunities", "get_opportunity") + OUTREACH,
    "prep": ("list_prep_items", "list_opportunities", "get_opportunity"),
    "resumes": (
        "list_resumes",
        "get_resume_profile",
        "search_resume",
        "list_opportunities",
        "get_opportunity",
        "which_resume_fits",
        "set_fit_score",
    ),
    "job_search": JOBS
    + FITS
    + ("set_fit_score", "get_pipeline_summary", "list_opportunities", "list_resumes"),
    "smalltalk": (),
}
ALL_TOOLS = (
    (
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
    )
    + WRITE
    + JOBS
    + FITS
    + OUTREACH
)


def toolset_for(intent: str | None) -> tuple[str, ...]:
    return TOOLSETS.get(intent or "", ALL_TOOLS)
