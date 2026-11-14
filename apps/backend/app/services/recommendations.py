"""A "Jobs for you" feed built from the user's resumes.

A refresh runs a few searches from the user's search profile (titles and places taken from
their resume profiles), embeds the new postings once, and ranks them by how close they sit to
the user's resume passages. No model call is made to rank: similarity is enough to order a
list, and a model is only used when the user asks "which resume fits this one?".
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    JobSearchError,
    MatchError,
    NotFoundError,
    QuotaError,
    RateLimitedError,
)
from app.llm.gateway import LLMGateway
from app.models.job_match import JobRecommendation, JobSearchProfile
from app.models.job_posting import JobPosting
from app.repositories.job_match import JobRecommendationRepository, JobSearchProfileRepository
from app.repositories.job_posting import JobPostingRepository
from app.repositories.resume import ResumeRepository
from app.repositories.resume_chunk import ResumeChunkRepository
from app.schemas.job import JobSearchRequest, Notice
from app.schemas.match import ProfileRead, ProfileUpdate, RecommendationRead, RefreshResponse
from app.services.assistant_access import ensure_opted_in
from app.services.job_search import JobSearchService
from app.services.rate_limit import RateLimiter

logger = logging.getLogger("app.recommendations")

DAY = timedelta(days=1)
EMBED_BATCH = 20
SCORED_PASSAGES = 3


class RecommendationService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        user_id: int,
        gateway: LLMGateway | None,
        jobs: JobSearchService,
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.user_id = user_id
        self.gateway = gateway
        self.jobs = jobs
        self.profiles = JobSearchProfileRepository(session, user_id)
        self.recs = JobRecommendationRepository(session, user_id)
        self.resumes = ResumeRepository(session, user_id)
        self.chunks = ResumeChunkRepository(session, user_id)
        self.postings = JobPostingRepository(session)
        self.limiter = RateLimiter(session, clock)

    # ---- the search profile ---------------------------------------------------------------

    def profile(self) -> JobSearchProfile:
        existing = self.profiles.mine()
        if existing is not None:
            return existing
        titles: list[str] = []
        places: list[str] = []
        derived: list[int] = []
        for resume in self.resumes.list(q=None, limit=50, offset=0):
            profile = resume.profile or {}
            if not profile:
                continue
            derived.append(resume.id)
            titles += [str(t) for t in profile.get("titles", [])]
            places += [str(p) for p in profile.get("locations", [])]
        created = self.profiles.add(
            JobSearchProfile(
                title_keywords=list(dict.fromkeys(t[:100] for t in titles if t.strip()))[:3],
                locations=list(dict.fromkeys(p[:100] for p in places if p.strip()))[:2],
                work_modes=[],
                min_vector_score=self.settings.match_min_vector_score,
                enabled=True,
                derived_from_resume_ids=derived,
            )
        )
        self.session.commit()
        return created

    def get_profile(self) -> ProfileRead:
        return ProfileRead.model_validate(self.profile())

    def update_profile(self, data: ProfileUpdate) -> ProfileRead:
        profile = self.profile()
        for field_name, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(profile, field_name, value)
        self.session.commit()
        return ProfileRead.model_validate(profile)

    # ---- the feed -------------------------------------------------------------------------

    def feed(self, limit: int | None = None) -> list[RecommendationRead]:
        limit = limit or self.settings.recommendations_max_items
        rows = self.recs.visible(limit * 2)
        tracked = self.jobs.queries.tracked([p.id for _, p in rows])
        rows = [(r, p) for r, p in rows if p.id not in tracked][:limit]
        reads = {j.id: j for j in self.jobs.reads([p for _, p in rows])}
        labels = {r.id: r.label for r in self.resumes.list(q=None, limit=100, offset=0)}
        return [
            RecommendationRead(
                id=rec.id,
                job=reads[posting.id],
                vector_score=rec.vector_score,
                best_resume_id=rec.best_resume_id,
                best_resume_label=labels.get(rec.best_resume_id) if rec.best_resume_id else None,
                created_at=rec.created_at,
            )
            for rec, posting in rows
        ]

    def dismiss(self, recommendation_id: int) -> None:
        rec = self.recs.get(recommendation_id)
        if rec is None:
            raise NotFoundError("Recommendation", recommendation_id)
        rec.dismissed = True
        self.session.commit()

    def refresh(self) -> RefreshResponse:
        ensure_opted_in(self.session, self.user_id)
        profile = self.profile()
        if not profile.enabled:
            raise MatchError("recommendations_off", "Jobs for you is switched off.", 409)
        if not profile.title_keywords:
            raise MatchError(
                "profile_empty",
                "Add a job title to your search profile (or upload a resume) first.",
                422,
            )
        if self.gateway is None or not self.gateway.enabled:
            raise MatchError(
                "assistant_disabled", "The AI assistant isn't set up on this server.", 503
            )
        if not self.jobs.enabled:
            raise JobSearchError(
                "job_search_disabled", "Job search isn't set up on this server yet.", 503
            )
        ready = [
            r.id
            for r in self.resumes.list(q=None, limit=100, offset=0)
            if r.storage_key and r.embed_status == "ready"
        ]
        if not ready:
            raise MatchError(
                "resumes_not_indexed",
                "None of your resumes is indexed yet. Upload a PDF and wait for it to finish.",
                409,
            )
        try:
            self.limiter.consume(
                f"recommendations:{self.user_id}",
                self.settings.recommendations_refresh_per_day,
                DAY,
            )
        except RateLimitedError as exc:
            raise QuotaError(
                "recommendations_quota",
                exc.retry_after_seconds,
                "You've refreshed Jobs for you as often as today allows. Try again tomorrow.",
            ) from exc
        self.session.commit()

        postings, notices = self._gather(profile)
        known = self.recs.existing_posting_ids()
        fresh = [p for p in postings if p.id not in known]
        scored = self._rank(fresh, ready, profile.min_vector_score)

        room = max(0, self.settings.recommendations_max_items - len(self.feed()))
        added = 0
        for posting, score, best in scored[:room]:
            self.recs.add(
                JobRecommendation(
                    job_posting_id=posting.id, best_resume_id=best, vector_score=round(score, 4)
                )
            )
            added += 1
        profile.last_refreshed_at = self.clock.now()
        self.session.commit()
        return RefreshResponse(added=added, considered=len(fresh), notices=notices)

    # ---- pieces ---------------------------------------------------------------------------

    def _gather(self, profile: JobSearchProfile) -> tuple[list[JobPosting], list[Notice]]:
        seen: dict[int, JobPosting] = {}
        notices: list[Notice] = []
        location = profile.locations[0] if profile.locations else None
        work_mode = profile.work_modes[0] if len(profile.work_modes) == 1 else None
        for keyword in profile.title_keywords[: self.settings.recommendations_max_queries]:
            try:
                found = self.jobs.search(
                    JobSearchRequest(
                        query=keyword,
                        location=location,
                        work_mode=work_mode,
                        posted_within_days=7,
                        limit=10,
                    ),
                    count_against_user=False,
                )
            except JobSearchError as exc:
                notices.append(Notice(code=exc.code, message=exc.message))
                break
            notices += [n for n in found.notices if n not in notices]
            for posting in self.postings.get_many([j.id for j in found.results]):
                seen.setdefault(posting.id, posting)
        return list(seen.values()), notices

    def _rank(
        self, postings: list[JobPosting], resume_ids: list[int], floor: float
    ) -> list[tuple[JobPosting, float, int | None]]:
        assert self.gateway is not None
        usable = [p for p in postings if (p.description or p.title)]
        scored: list[tuple[JobPosting, float, int | None]] = []
        for start in range(0, len(usable), EMBED_BATCH):
            batch = usable[start : start + EMBED_BATCH]
            vectors = self.gateway.embed(
                [f"{p.title} at {p.company}. {(p.description or '')[:1500]}" for p in batch],
                kind="query",
            )
            for posting, vector in zip(batch, vectors, strict=True):
                hits = self.chunks.similar(vector, resume_ids=resume_ids, k=SCORED_PASSAGES)
                if not hits:
                    continue
                score = sum(h.score for h in hits) / len(hits)
                if score >= floor:
                    scored.append((posting, score, hits[0].resume_id))
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored
