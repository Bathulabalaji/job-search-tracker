"""Tavily web search, limited to applicant-tracking and career sites. It finds postings on
company career pages that the job boards miss. Results are web pages, not structured jobs,
so company and title are read from the page title. Free plan: 1,000 credits a month."""

import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.jobsearch.base import JobHit, ProviderQuota, SearchParams
from app.jobsearch.http import get_json, text
from app.jobsearch.normalize import detect_work_mode, strip_html

ATS_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "workable.com",
    "zohorecruit.com",
    "zohorecruit.in",
    "keka.com",
    "darwinbox.in",
    "freshteam.com",
    "recruitee.com",
    "bamboohr.com",
    "jobvite.com",
    "icims.com",
]
COUNTRY_NAMES = {"in": "india", "us": "united states", "gb": "united kingdom"}
_SPLIT = re.compile(r"\s+(?:[-–—|@]|at)\s+")
# Greenhouse: boards.greenhouse.io/{company}/jobs/{id}; Lever: jobs.lever.co/{company}/{id}
_SLUG_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "recruitee.com")


def time_range(days: int) -> str:
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    return "year"


class TavilyProvider:
    name = "tavily"

    def __init__(
        self, client: httpx.Client, api_key: str, *, monthly_quota: int, timeout: float
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.timeout = timeout
        self.quota = ProviderQuota(monthly_quota, "month")

    def search(self, params: SearchParams) -> list[JobHit]:
        parts = [params.query, "job opening"]
        if params.location:
            parts.append(params.location)
        if params.work_mode == "remote":
            parts.append("remote")
        request: dict[str, Any] = {
            "query": " ".join(parts),
            "search_depth": "basic",
            "max_results": min(max(params.limit * 2, 5), 15),
            "include_domains": ATS_DOMAINS,
            "time_range": time_range(params.posted_within_days),
        }
        country = COUNTRY_NAMES.get(params.country.lower())
        if country:
            request["country"] = country
        body = get_json(
            self.client,
            "POST",
            "https://api.tavily.com/search",
            json=request,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        return [hit for item in body.get("results") or [] if (hit := _hit(item)) is not None]


def _hit(item: dict[str, Any]) -> JobHit | None:
    url = text(item.get("url"))
    page_title = text(item.get("title"))
    if not (url and page_title):
        return None
    if not _looks_like_posting(url):
        return None
    title, company = _split_title(page_title, url)
    if not company:
        return None
    description = strip_html(text(item.get("content")))
    return JobHit(
        provider="tavily",
        external_id=url[:200],
        title=title,
        company=company,
        url=url,
        location=None,
        posted_at=None,
        description=description,
        work_mode=detect_work_mode(page_title, description),
        via="Company career page",
        raw={"score": item.get("score")},
    )


def _looks_like_posting(url: str) -> bool:
    """A job page has an id-ish last segment, not just the board's front page."""
    path = [p for p in urlsplit(url).path.split("/") if p]
    return len(path) >= 2 or bool(re.search(r"\d{4,}", url))


def _split_title(page_title: str, url: str) -> tuple[str, str | None]:
    cleaned = re.sub(r"^(job application for|jobs? at)\s+", "", page_title, flags=re.I).strip()
    parts = [p.strip() for p in _SPLIT.split(cleaned) if p.strip()]
    slug = _company_from_url(url)
    if len(parts) >= 2:
        title, company = parts[0], parts[1]
        if slug and slug.lower() in parts[0].lower() and len(parts) == 2:
            title, company = parts[1], parts[0]
        return title[:300], company[:200]
    return cleaned[:300], slug


def _company_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    segments = [p for p in parts.path.split("/") if p]
    if any(host.endswith(h) for h in _SLUG_HOSTS) and segments:
        return segments[0].replace("-", " ").title()
    sub = host.split(".")[0]
    if sub not in ("www", "jobs", "careers", "boards", "apply") and len(host.split(".")) > 2:
        return sub.replace("-", " ").title()
    return None
