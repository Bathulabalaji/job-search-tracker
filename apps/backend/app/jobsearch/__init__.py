"""Job search over public search APIs (Phase 3). See base.py for the provider contract."""

from functools import lru_cache

import httpx

from app.core.clock import Clock
from app.core.config import Settings
from app.jobsearch.active_check import ActiveChecker
from app.jobsearch.adzuna import AdzunaProvider
from app.jobsearch.base import JobHit, JobSearchProvider, ProviderError, SearchParams
from app.jobsearch.jsearch import JSearchProvider
from app.jobsearch.serpapi import SerpApiProvider
from app.jobsearch.tavily import TavilyProvider


@lru_cache
def _client() -> httpx.Client:
    # Shared and thread-safe: one connection pool for every provider and the link checker.
    return httpx.Client(follow_redirects=False, headers={"Accept": "application/json"})


def build_job_search_providers(
    settings: Settings, clock: Clock, client: httpx.Client | None = None
) -> list[JobSearchProvider]:
    """The configured providers, in JOBSEARCH_PROVIDER_ORDER. Blank keys are skipped."""
    http = client or _client()
    timeout = settings.jobsearch_timeout_seconds
    available: dict[str, JobSearchProvider] = {}
    if settings.adzuna_app_id and settings.adzuna_app_key:
        available["adzuna"] = AdzunaProvider(
            http,
            settings.adzuna_app_id,
            settings.adzuna_app_key,
            daily_quota=settings.jobsearch_adzuna_daily_quota,
            timeout=timeout,
        )
    if settings.rapidapi_key:
        available["jsearch"] = JSearchProvider(
            http,
            settings.rapidapi_key,
            monthly_quota=settings.jobsearch_jsearch_monthly_quota,
            timeout=timeout,
        )
    if settings.serpapi_key:
        available["serpapi"] = SerpApiProvider(
            http,
            settings.serpapi_key,
            clock,
            monthly_quota=settings.jobsearch_serpapi_monthly_quota,
            timeout=timeout,
        )
    if settings.tavily_api_key:
        available["tavily"] = TavilyProvider(
            http,
            settings.tavily_api_key,
            monthly_quota=settings.jobsearch_tavily_monthly_quota,
            timeout=timeout,
        )
    order = [n.strip().lower() for n in settings.jobsearch_provider_order.split(",") if n.strip()]
    ordered = [available.pop(n) for n in order if n in available]
    return ordered + list(available.values())


def build_active_checker(settings: Settings) -> ActiveChecker | None:
    if not settings.job_active_check_enabled:
        return None
    return ActiveChecker(_client(), timeout=settings.job_active_check_timeout_seconds)


__all__ = [
    "ActiveChecker",
    "JobHit",
    "JobSearchProvider",
    "ProviderError",
    "SearchParams",
    "build_active_checker",
    "build_job_search_providers",
]
