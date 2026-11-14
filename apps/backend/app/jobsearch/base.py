"""What every job-search provider looks like to the rest of the app.

Providers are search APIs only (Adzuna, JSearch, SerpApi, Tavily). Nothing here scrapes a job
board: LinkedIn and Naukri postings arrive through Google-for-Jobs aggregators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

Period = Literal["day", "month"]
ErrorKind = Literal["quota", "auth", "unavailable", "bad_request"]


@dataclass(frozen=True)
class SearchParams:
    query: str
    location: str | None = None
    work_mode: str | None = None  # remote | hybrid | onsite
    posted_within_days: int = 7
    limit: int = 5
    country: str = "in"


@dataclass(frozen=True)
class ProviderQuota:
    limit: int
    period: Period


@dataclass
class JobHit:
    """One posting as a provider returned it, before normalisation and dedupe."""

    provider: str
    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    posted_at: datetime | None = None
    description: str | None = None
    salary_text: str | None = None
    work_mode: str | None = None
    # The site the provider says it came from ("LinkedIn", "via Naukri.com"...).
    via: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    """A provider call that did not produce results, classified so the caller can fall
    through to the next provider (and park this one when its quota is spent)."""

    def __init__(self, kind: ErrorKind, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind


class JobSearchProvider(Protocol):
    name: str
    quota: ProviderQuota

    def search(self, params: SearchParams) -> list[JobHit]: ...
