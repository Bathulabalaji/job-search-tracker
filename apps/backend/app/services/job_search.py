"""Job search across free search APIs, with the budget kept honest.

A live search walks the providers in order and stops once it has enough distinct postings.
Each provider's free quota (per day or per month) is counted in the provider ledger before
the call is made, so a quota can't be overrun however many users search at once. An identical
search by the same user within JOB_QUERY_CACHE_HOURS is answered from the cache for free.
When every provider is spent, recent cached postings are offered with a notice instead.
"""

import hashlib
import json
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    JobSearchError,
    JobSearchQuotaError,
    NotFoundError,
    RateLimitedError,
)
from app.jobsearch.active_check import ActiveChecker
from app.jobsearch.base import JobHit, JobSearchProvider, ProviderError, ProviderQuota, SearchParams
from app.jobsearch.normalize import canonical_url, dedupe, fingerprint, source_site
from app.jobsearch.sanitize import clean_description
from app.models.enums import Source, Stage, WorkMode
from app.models.job_posting import JobPosting, JobSearchQuery
from app.models.provider_ledger import ProviderUsageEvent
from app.repositories.job_posting import JobPostingRepository
from app.repositories.job_search_query import JobSearchQueryRepository
from app.repositories.provider_ledger import ProviderLedgerRepository
from app.schemas.job import (
    JobPostingRead,
    JobSearchRequest,
    JobSearchResponse,
    Notice,
    TrackJobRequest,
)
from app.schemas.opportunity import OpportunityCreate, OpportunityRead
from app.services.opportunity import OpportunityService
from app.services.rate_limit import RateLimiter

logger = logging.getLogger("app.jobsearch")

DAY = timedelta(days=1)
RECHECK_AFTER = timedelta(hours=12)
AUTH_COOLDOWN = timedelta(hours=1)
UNAVAILABLE_COOLDOWN = timedelta(minutes=2)
STACK_KEYWORDS = (
    "python", "fastapi", "django", "flask", "java", "spring", "kotlin", "golang", "rust",
    "node", "typescript", "javascript", "react", "next.js", "angular", "vue", "postgresql",
    "mysql", "mongodb", "redis", "kafka", "rabbitmq", "graphql", "aws", "gcp", "azure",
    "docker", "kubernetes", "terraform", "spark", "airflow", "pytorch", "tensorflow", "llm",
    "langchain", "machine learning", "data engineering", "microservices", "c++", "c#", ".net",
    "flutter", "android", "ios", "swift",
)  # fmt: skip
SOURCE_FOR_SITE = {"linkedin": Source.linkedin, "naukri": Source.naukri}
PAUSED = Notice(
    code="search_paused",
    message=(
        "Live job search is paused for now (free-tier limits). "
        "These are recent cached results; try again later for fresh ones."
    ),
)
NOTHING_LIVE = Notice(
    code="search_unavailable",
    message="I couldn't reach the job-search services just now, so nothing new came back.",
)


@dataclass(frozen=True)
class _Outcome:
    hits: list[JobHit]
    used: list[str]
    any_live: bool


def stack_tags(*texts: str | None, limit: int = 8) -> list[str]:
    """Known technologies mentioned in the title or description, as opportunity tags."""
    joined = " ".join(t for t in texts if t).lower()
    tags: list[str] = []
    for word in STACK_KEYWORDS:
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", joined):
            tag = "go" if word == "golang" else word
            if tag not in tags:
                tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _cap(value: str | None, size: int) -> str | None:
    return value[:size] if value else None


def window_start(now: datetime, quota: ProviderQuota) -> datetime:
    utc = now.astimezone(UTC)
    if quota.period == "day":
        return utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def window_end(now: datetime, quota: ProviderQuota) -> datetime:
    start = window_start(now, quota)
    if quota.period == "day":
        return start + DAY
    return (start + timedelta(days=32)).replace(day=1)


class JobSearchService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        user_id: int,
        providers: Sequence[JobSearchProvider],
        checker: ActiveChecker | None,
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.user_id = user_id
        self.providers = list(providers)
        self.checker = checker
        self.postings = JobPostingRepository(session)
        self.queries = JobSearchQueryRepository(session, user_id)
        self.ledger = ProviderLedgerRepository(session)
        self.limiter = RateLimiter(session, clock)

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    # ---- search ---------------------------------------------------------------------------

    def search(self, request: JobSearchRequest) -> JobSearchResponse:
        if not self.providers:
            raise JobSearchError(
                "job_search_disabled", "Job search isn't set up on this server yet.", 503
            )
        now = self.clock.now()
        params = SearchParams(
            query=request.query,
            location=request.location,
            work_mode=request.work_mode,
            posted_within_days=request.posted_within_days,
            limit=request.limit,
            country=self.settings.jobsearch_country,
        )
        key = cache_key(params)
        cached = self._from_cache(key, now)
        if cached is not None:
            return cached
        try:
            self.limiter.consume(
                f"job-search:{self.user_id}", self.settings.chat_search_daily_limit, DAY
            )
        except RateLimitedError as exc:
            limit = self.settings.chat_search_daily_limit
            raise JobSearchQuotaError(
                exc.retry_after_seconds,
                f"You've used today's {limit} job searches. Try again tomorrow.",
            ) from exc
        self.session.commit()

        outcome = self._live(params)
        notices: list[Notice] = []
        if outcome.hits:
            postings = self._store(outcome.hits, params, now)
        else:
            postings = []
        if not outcome.any_live:
            words = [w for w in request.query.lower().split() if len(w) > 2][:4]
            postings = self.postings.search_cached(words, now, params.limit)
            notices.append(PAUSED if postings else NOTHING_LIVE)
        postings = postings[: params.limit]
        self._check_active(postings, now)
        self.queries.add(
            JobSearchQuery(
                cache_key=key,
                query_text=request.query,
                params=request.model_dump(mode="json"),
                providers_used=outcome.used,
                result_ids=[p.id for p in postings],
                notices=[n.model_dump() for n in notices] or None,
                created_at=now,
            )
        )
        self.session.commit()
        return JobSearchResponse(
            results=self._reads(postings),
            from_cache=False,
            providers_used=outcome.used,
            notices=notices,
        )

    def _from_cache(self, key: str, now: datetime) -> JobSearchResponse | None:
        since = now - timedelta(hours=self.settings.job_query_cache_hours)
        previous = self.queries.recent(key, since)
        if previous is None or not previous.result_ids:
            return None
        postings = self.postings.get_many(previous.result_ids)
        if len(postings) != len(previous.result_ids):
            return None  # some were pruned: search again
        return JobSearchResponse(
            results=self._reads(postings),
            from_cache=True,
            providers_used=list(previous.providers_used),
            notices=[Notice.model_validate(n) for n in previous.notices or []],
        )

    def _live(self, params: SearchParams) -> _Outcome:
        """Walk the providers until there are enough distinct, fresh postings."""
        hits: list[JobHit] = []
        used: list[str] = []
        any_live = False
        cutoff = self.clock.now() - timedelta(days=params.posted_within_days + 1)
        for provider in self.providers:
            event = self._reserve(provider)
            if event is None:
                continue
            started = time.monotonic()
            try:
                found = provider.search(params)
            except ProviderError as exc:
                self._settle(provider, event, started, exc.kind)
                logger.warning(
                    "job_search_provider_failed",
                    extra={"provider": provider.name, "kind": exc.kind},
                )
                continue
            except Exception:
                self._settle(provider, event, started, "unavailable")
                logger.exception("job_search_provider_crashed", extra={"provider": provider.name})
                continue
            self._settle(provider, event, started, "ok")
            any_live = True
            used.append(provider.name)
            hits.extend(h for h in found if h.posted_at is None or h.posted_at >= cutoff)
            if len(dedupe(hits)) >= params.limit:
                break
        distinct = dedupe(hits)
        distinct.sort(
            key=lambda h: (
                h.posted_at is not None,
                h.posted_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        return _Outcome(distinct, used, any_live)

    # ---- provider budget ------------------------------------------------------------------

    def _resource(self, provider: JobSearchProvider) -> str:
        return f"search:{provider.name}"

    def _reserve(self, provider: JobSearchProvider) -> ProviderUsageEvent | None:
        """Count the call against the provider's quota before making it. The state row lock
        makes check-then-insert atomic across workers; it is released by the commit."""
        now = self.clock.now()
        resource = self._resource(provider)
        state = self.ledger.lock(resource, provider.name)
        if state.cooldown_until is not None and state.cooldown_until > now:
            self.session.commit()
            return None
        used = self.ledger.count_events(resource, window_start(now, provider.quota))
        if used >= provider.quota.limit:
            state.cooldown_until = window_end(now, provider.quota)
            state.cooldown_reason = "quota"
            self.session.commit()
            return None
        event = ProviderUsageEvent(
            created_at=now,
            user_id=self.user_id,
            kind="search",
            provider=provider.name,
            resource=resource,
            task="job_search",
            outcome="pending",
        )
        self.ledger.add_event(event)
        self.session.commit()
        return event

    def _settle(
        self, provider: JobSearchProvider, event: ProviderUsageEvent, started: float, kind: str
    ) -> None:
        now = self.clock.now()
        event.latency_ms = int((time.monotonic() - started) * 1000)
        event.outcome = {"ok": "ok", "quota": "quota", "auth": "error"}.get(kind, "error")
        event.error_code = None if kind == "ok" else kind
        state = self.ledger.lock(self._resource(provider), provider.name)
        if kind == "ok":
            state.consecutive_failures = 0
        elif kind == "quota":
            # The provider says the free tier is spent, whatever our count thought.
            state.cooldown_until = window_end(now, provider.quota)
            state.cooldown_reason = "quota"
        elif kind == "auth":
            state.cooldown_until = now + AUTH_COOLDOWN
            state.cooldown_reason = "auth"
            logger.error("job_search_provider_auth_failed", extra={"provider": provider.name})
        else:
            state.consecutive_failures += 1
            state.last_failure_at = now
            if state.consecutive_failures >= 3:
                state.cooldown_until = now + UNAVAILABLE_COOLDOWN
                state.cooldown_reason = "unavailable"
        self.session.commit()

    # ---- persistence ----------------------------------------------------------------------

    def _store(self, hits: list[JobHit], params: SearchParams, now: datetime) -> list[JobPosting]:
        expires = now + timedelta(hours=self.settings.job_cache_ttl_hours)
        stored: list[JobPosting] = []
        seen: set[int] = set()
        for hit in hits:
            url = canonical_url(hit.url)
            fp = fingerprint(hit.company, hit.title, hit.location)
            description, flagged = clean_description(hit.description)
            if flagged:
                logger.warning("job_injection_suspected", extra={"provider": hit.provider})
            site = source_site(hit.url, hit.via)
            posting = self.postings.find(url, fp)
            if posting is None:
                posting = self.postings.add(
                    JobPosting(
                        provider=hit.provider,
                        external_id=hit.external_id[:200],
                        canonical_url=url[:1000],
                        fingerprint=fp,
                        title=hit.title[:300],
                        company=hit.company[:200],
                        location=_cap(hit.location, 200),
                        country=params.country[:2],
                        work_mode=hit.work_mode,
                        source_site=site,
                        apply_url=hit.url[:1000],
                        posted_at=hit.posted_at,
                        salary_text=_cap(hit.salary_text, 200),
                        description=description,
                        raw={**hit.raw, "via": hit.via, "flagged": flagged or None},
                        fetched_at=now,
                        expires_at=expires,
                    )
                )
            else:
                posting.title = hit.title[:300]
                posting.company = hit.company[:200]
                posting.location = _cap(hit.location, 200) or posting.location
                posting.work_mode = hit.work_mode or posting.work_mode
                posting.posted_at = hit.posted_at or posting.posted_at
                posting.salary_text = _cap(hit.salary_text, 200) or posting.salary_text
                if description and len(description) > len(posting.description or ""):
                    posting.description = description
                posting.fetched_at = now
                posting.expires_at = expires
                self.session.flush()
            if posting.id in seen:
                continue
            seen.add(posting.id)
            stored.append(posting)
        return stored

    def _check_active(self, postings: list[JobPosting], now: datetime) -> None:
        if self.checker is None:
            return
        due = [
            p
            for p in postings[:5]
            if p.active_checked_at is None or now - p.active_checked_at > RECHECK_AFTER
        ]
        if not due:
            return
        verdicts = self.checker.check_many([p.apply_url for p in due])
        for posting in due:
            verdict = verdicts.get(posting.apply_url, "unknown")
            # A throttled or blocked re-check says nothing new: keep the last real verdict
            # rather than downgrading it to "unknown" (the back-off in checked_at still applies).
            if verdict != "unknown" or posting.active_status == "unknown":
                posting.active_status = verdict
            posting.active_checked_at = now
        self.session.flush()

    def _reads(self, postings: list[JobPosting], *, full: bool = False) -> list[JobPostingRead]:
        tracked = self.queries.tracked([p.id for p in postings])
        reads: list[JobPostingRead] = []
        for p in postings:
            read = JobPostingRead.model_validate(p)
            reads.append(
                read.model_copy(
                    update={
                        "tracked_opportunity_id": tracked.get(p.id),
                        "description": p.description if full else None,
                    }
                )
            )
        return reads

    # ---- one posting ----------------------------------------------------------------------

    def _posting(self, posting_id: int) -> JobPosting:
        posting = self.postings.get(posting_id)
        if posting is None:
            raise NotFoundError("Job posting", posting_id)
        return posting

    def get(self, posting_id: int) -> JobPostingRead:
        return self._reads([self._posting(posting_id)], full=True)[0]

    def check(self, posting_id: int) -> JobPostingRead:
        posting = self._posting(posting_id)
        if self.checker is not None:
            posting.active_status = self.checker.check(posting.apply_url)
            posting.active_checked_at = self.clock.now()
            self.session.commit()
        return self._reads([posting])[0]

    def track(self, posting_id: int, request: TrackJobRequest) -> OpportunityRead:
        posting = self._posting(posting_id)
        existing = self.queries.tracked([posting.id]).get(posting.id)
        if existing is not None:
            raise JobSearchError("already_tracked", "This job is already in your pipeline.", 409)
        modes = {m.value: m for m in WorkMode}
        work_mode = modes.get(posting.work_mode or "")
        data = OpportunityCreate(
            company=posting.company[:200],
            role=posting.title[:200],
            source=SOURCE_FOR_SITE.get(posting.source_site, Source.other),
            stack_tags=stack_tags(posting.title, posting.description),
            location=posting.location,
            work_mode=work_mode,
            stage=Stage(request.stage),
            priority=request.priority,
            jd_text=posting.description,
            jd_url=posting.apply_url[:1000],
        )
        try:
            return OpportunityService(self.session, self.clock, self.settings, self.user_id).create(
                data, job_posting_id=posting.id
            )
        except IntegrityError as exc:  # a double click raced the check above
            self.session.rollback()
            raise JobSearchError(
                "already_tracked", "This job is already in your pipeline.", 409
            ) from exc


def cache_key(params: SearchParams) -> str:
    payload = {
        "q": params.query.lower(),
        "loc": (params.location or "").lower(),
        "mode": params.work_mode,
        "days": params.posted_within_days,
        "limit": params.limit,
        "country": params.country.lower(),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
