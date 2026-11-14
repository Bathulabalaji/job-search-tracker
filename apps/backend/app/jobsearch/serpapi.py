"""SerpApi's Google Jobs engine. Free plan: about 250 searches a month.

Google no longer supports a date filter (`chips`) or the remote filter (`ltype`), so freshness
and work mode are applied after the fact from `detected_extensions`.
"""

from datetime import datetime
from typing import Any

import httpx

from app.core.clock import Clock
from app.jobsearch.base import JobHit, ProviderQuota, SearchParams
from app.jobsearch.http import get_json, text
from app.jobsearch.normalize import detect_work_mode, parse_relative, strip_html

COUNTRY_NAMES = {"in": "India", "us": "United States", "gb": "United Kingdom"}


class SerpApiProvider:
    name = "serpapi"

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        clock: Clock,
        *,
        monthly_quota: int,
        timeout: float,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.clock = clock
        self.timeout = timeout
        self.quota = ProviderQuota(monthly_quota, "month")

    def search(self, params: SearchParams) -> list[JobHit]:
        q = params.query if params.work_mode != "remote" else f"{params.query} remote"
        request: dict[str, Any] = {
            "engine": "google_jobs",
            "q": q,
            "gl": params.country.lower(),
            "hl": "en",
            "api_key": self.api_key,
        }
        request["location"] = params.location or COUNTRY_NAMES.get(params.country.lower(), "")
        if not request["location"]:
            del request["location"]
        body = get_json(
            self.client,
            "GET",
            "https://serpapi.com/search.json",
            params=request,
            timeout=self.timeout,
        )
        now = self.clock.now()
        return [
            hit for item in body.get("jobs_results") or [] if (hit := _hit(item, now)) is not None
        ]


def _hit(item: dict[str, Any], now: datetime) -> JobHit | None:
    title = text(item.get("title"))
    company = text(item.get("company_name"))
    options = [o for o in item.get("apply_options") or [] if isinstance(o, dict)]
    url = next((text(o.get("link")) for o in options if text(o.get("link"))), None)
    url = url or text(item.get("share_link"))
    if not (title and company and url):
        return None
    ext = item.get("detected_extensions") or {}
    location = text(item.get("location"))
    description = strip_html(text(item.get("description")))
    remote = ext.get("work_from_home") is True
    return JobHit(
        provider="serpapi",
        external_id=str(item.get("job_id") or url)[:200],
        title=title,
        company=company,
        url=url,
        location=location,
        posted_at=parse_relative(text(ext.get("posted_at")), now),
        description=description,
        salary_text=text(ext.get("salary")),
        work_mode="remote" if remote else detect_work_mode(title, location, description),
        via=text(item.get("via")),
        raw={"via": item.get("via"), "posted_at": ext.get("posted_at")},
    )
