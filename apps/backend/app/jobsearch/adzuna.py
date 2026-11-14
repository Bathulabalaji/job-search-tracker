"""Adzuna: a job aggregator with an India feed. Free key: about 250 calls a day."""

from datetime import datetime
from typing import Any

import httpx

from app.jobsearch.base import JobHit, ProviderQuota, SearchParams
from app.jobsearch.http import get_json, text
from app.jobsearch.normalize import detect_work_mode, strip_html

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaProvider:
    name = "adzuna"

    def __init__(
        self, client: httpx.Client, app_id: str, app_key: str, *, daily_quota: int, timeout: float
    ) -> None:
        self.client = client
        self.app_id = app_id
        self.app_key = app_key
        self.timeout = timeout
        self.quota = ProviderQuota(daily_quota, "day")

    def search(self, params: SearchParams) -> list[JobHit]:
        what = params.query
        if params.work_mode == "remote":
            what = f"{what} remote"
        query: dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": what,
            "results_per_page": min(max(params.limit * 2, 10), 20),
            "max_days_old": params.posted_within_days,
            "sort_by": "date",
            "content-type": "application/json",
        }
        if params.location:
            query["where"] = params.location
        body = get_json(
            self.client,
            "GET",
            f"{BASE_URL}/{params.country.lower()}/search/1",
            params=query,
            timeout=self.timeout,
        )
        return [hit for item in body.get("results") or [] if (hit := _hit(item)) is not None]


def _hit(item: dict[str, Any]) -> JobHit | None:
    title = text(item.get("title"))
    url = text(item.get("redirect_url"))
    company = text((item.get("company") or {}).get("display_name"))
    if not (title and url and company):
        return None
    location = text((item.get("location") or {}).get("display_name"))
    description = strip_html(text(item.get("description")))
    return JobHit(
        provider="adzuna",
        external_id=str(item.get("id") or url),
        title=strip_html(title) or title,
        company=company,
        url=url,
        location=location,
        posted_at=_parse(item.get("created")),
        description=description,
        salary_text=_salary(item),
        work_mode=detect_work_mode(title, location, description),
        via="Adzuna",
        raw={k: item.get(k) for k in ("id", "created", "contract_time", "category")},
    )


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _salary(item: dict[str, Any]) -> str | None:
    low, high = item.get("salary_min"), item.get("salary_max")
    if not isinstance(low, int | float) or item.get("salary_is_predicted") in ("1", 1, True):
        return None
    if isinstance(high, int | float) and high > low:
        return f"{low:,.0f}–{high:,.0f} a year"
    return f"{low:,.0f} a year"
