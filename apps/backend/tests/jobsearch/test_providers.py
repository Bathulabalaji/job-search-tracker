from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.core.clock import Clock
from app.jobsearch.adzuna import AdzunaProvider
from app.jobsearch.base import ProviderError, SearchParams
from app.jobsearch.jsearch import JSearchProvider
from app.jobsearch.serpapi import SerpApiProvider
from app.jobsearch.tavily import TavilyProvider
from tests.jobsearch.helpers import fixture, mock_client

PARAMS = SearchParams(query="python backend", location="Bengaluru", posted_within_days=7, limit=5)
NOW = datetime(2026, 11, 11, 4, 30, tzinfo=UTC)


def test_adzuna_maps_the_india_feed_and_skips_incomplete_rows() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=fixture("adzuna"))

    provider = AdzunaProvider(mock_client(handler), "id", "key", daily_quota=10, timeout=5)
    hits = provider.search(PARAMS)

    url = seen[0].url
    assert url.path == "/v1/api/jobs/in/search/1"
    assert url.params["what"] == "python backend" and url.params["where"] == "Bengaluru"
    assert url.params["max_days_old"] == "7" and url.params["sort_by"] == "date"
    assert [h.company for h in hits] == ["Zepto", "Swiggy"]
    zepto = hits[0]
    assert zepto.title == "Senior Python Backend Engineer"
    assert zepto.posted_at == datetime(2026, 11, 9, 6, 12, tzinfo=UTC)
    assert zepto.salary_text == "2,500,000–4,000,000 a year"
    assert zepto.work_mode == "hybrid"
    assert hits[1].salary_text is None  # predicted salaries are not shown as facts


def test_jsearch_prefers_the_direct_apply_link_and_reads_both_date_formats() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=fixture("jsearch"))

    provider = JSearchProvider(mock_client(handler), "k", monthly_quota=10, timeout=5)
    hits = provider.search(PARAMS)

    request = seen[0]
    assert request.headers["X-RapidAPI-Host"] == "jsearch.p.rapidapi.com"
    assert request.url.params["query"] == "python backend in Bengaluru"
    assert request.url.params["date_posted"] == "week" and request.url.params["country"] == "in"
    zepto, razorpay = hits
    assert zepto.url == "https://careers.zepto.com/jobs/123?utm_source=google"
    assert zepto.via == "LinkedIn" and zepto.location == "Bengaluru, Karnataka"
    assert zepto.posted_at == datetime.fromtimestamp(1762750000, UTC)
    assert razorpay.work_mode == "remote"
    assert razorpay.posted_at == datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
    assert razorpay.salary_text == "1,500,000–2,500,000 year"


def test_serpapi_reads_relative_dates_and_falls_back_to_nothing_without_a_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["engine"] == "google_jobs"
        assert request.url.params["location"] == "Bengaluru"
        assert "chips" not in request.url.params  # deprecated by Google
        return httpx.Response(200, json=fixture("serpapi"))

    clock = Clock(tz=ZoneInfo("Asia/Kolkata"), now_fn=lambda: NOW)
    provider = SerpApiProvider(mock_client(handler), "k", clock, monthly_quota=10, timeout=5)
    [cred] = provider.search(PARAMS)  # Meesho has no apply link or share link
    assert cred.company == "CRED" and cred.via == "Instahyre"
    assert cred.posted_at == datetime(2026, 11, 8, 4, 30, tzinfo=UTC)
    assert cred.work_mode == "remote"


def test_tavily_keeps_posting_pages_and_reads_company_from_the_title() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert request.headers["Authorization"] == "Bearer k"
        assert '"time_range":"week"' in body.replace(" ", "")
        assert "greenhouse.io" in body
        return httpx.Response(200, json=fixture("tavily"))

    provider = TavilyProvider(mock_client(handler), "k", monthly_quota=10, timeout=5)
    hits = provider.search(PARAMS)
    assert [(h.title, h.company) for h in hits] == [
        ("Backend Engineer", "Postman"),
        ("Senior Software Engineer, Payments", "Razorpay"),
    ]
    assert hits[0].work_mode == "hybrid"


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, "quota"),
        (402, "quota"),
        (403, "auth"),
        (401, "auth"),
        (500, "unavailable"),
        (400, "bad_request"),
    ],
)
def test_http_failures_are_classified(status: int, kind: str) -> None:
    client = mock_client(lambda _: httpx.Response(status, json={}))
    provider = JSearchProvider(client, "k", monthly_quota=10, timeout=5)
    with pytest.raises(ProviderError) as caught:
        provider.search(PARAMS)
    assert caught.value.kind == kind


def test_timeouts_and_garbage_are_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    for client in (mock_client(timeout), mock_client(lambda _: httpx.Response(200, text="<html>"))):
        provider = AdzunaProvider(client, "id", "key", daily_quota=10, timeout=5)
        with pytest.raises(ProviderError) as caught:
            provider.search(PARAMS)
        assert caught.value.kind == "unavailable"
