"""JSearch (RapidAPI): Google for Jobs results, so LinkedIn, Naukri and company career pages.
Free plan: about 200 requests a month, hence it is not first in line."""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.jobsearch.base import JobHit, ProviderQuota, SearchParams
from app.jobsearch.http import get_json, text
from app.jobsearch.normalize import detect_work_mode, strip_html

HOST = "jsearch.p.rapidapi.com"


def date_posted(days: int) -> str:
    if days <= 1:
        return "today"
    if days <= 3:
        return "3days"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    return "all"


class JSearchProvider:
    name = "jsearch"

    def __init__(
        self, client: httpx.Client, api_key: str, *, monthly_quota: int, timeout: float
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.timeout = timeout
        self.quota = ProviderQuota(monthly_quota, "month")

    def search(self, params: SearchParams) -> list[JobHit]:
        query = params.query if not params.location else f"{params.query} in {params.location}"
        request: dict[str, Any] = {
            "query": query,
            "page": 1,
            "num_pages": 1,
            "date_posted": date_posted(params.posted_within_days),
            "country": params.country.lower(),
        }
        if params.work_mode == "remote":
            request["work_from_home"] = "true"
        body = get_json(
            self.client,
            "GET",
            f"https://{HOST}/search",
            params=request,
            headers={"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": HOST},
            timeout=self.timeout,
        )
        return [hit for item in body.get("data") or [] if (hit := _hit(item)) is not None]


def _hit(item: dict[str, Any]) -> JobHit | None:
    title = text(item.get("job_title"))
    company = text(item.get("employer_name"))
    url = _apply_link(item)
    if not (title and company and url):
        return None
    location = text(item.get("job_location")) or ", ".join(
        p for p in (text(item.get("job_city")), text(item.get("job_state"))) if p
    )
    description = strip_html(text(item.get("job_description")))
    remote = item.get("job_is_remote") is True
    return JobHit(
        provider="jsearch",
        external_id=str(item.get("job_id") or url),
        title=title,
        company=company,
        url=url,
        location=location or None,
        posted_at=_posted(item),
        description=description,
        salary_text=_salary(item),
        work_mode="remote" if remote else detect_work_mode(title, location, description),
        via=text(item.get("job_publisher")),
        raw={k: item.get(k) for k in ("job_id", "job_publisher", "job_employment_type")},
    )


def _apply_link(item: dict[str, Any]) -> str | None:
    """Prefer a direct apply option (the company's own page) over a board's redirect."""
    options = item.get("apply_options") or []
    for option in options:
        if isinstance(option, dict) and option.get("is_direct") and text(option.get("apply_link")):
            return text(option.get("apply_link"))
    return text(item.get("job_apply_link")) or text(item.get("job_google_link"))


def _posted(item: dict[str, Any]) -> datetime | None:
    stamp = item.get("job_posted_at_timestamp")
    if isinstance(stamp, int | float) and stamp > 0:
        return datetime.fromtimestamp(stamp, UTC)
    value = item.get("job_posted_at_datetime_utc")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _salary(item: dict[str, Any]) -> str | None:
    low, high = item.get("job_min_salary"), item.get("job_max_salary")
    period = text(item.get("job_salary_period")) or ""
    if not isinstance(low, int | float):
        return None
    span = (
        f"{low:,.0f}–{high:,.0f}" if isinstance(high, int | float) and high > low else f"{low:,.0f}"
    )
    return f"{span} {period.lower()}".strip()
