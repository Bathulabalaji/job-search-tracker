import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from app.jobsearch.base import JobHit, ProviderError, ProviderQuota, SearchParams

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict[str, Any]:
    return dict(json.loads((FIXTURES / f"{name}.json").read_text()))


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class FakeJobProvider:
    """Scripted provider: each search returns the next scripted result (hits or an error)."""

    def __init__(self, name: str, *steps: list[JobHit] | ProviderError, limit: int = 100) -> None:
        self.name = name
        self.quota = ProviderQuota(limit, "month")
        self.steps = list(steps)
        self.calls: list[SearchParams] = []

    def search(self, params: SearchParams) -> list[JobHit]:
        self.calls.append(params)
        step = self.steps.pop(0) if self.steps else []
        if isinstance(step, ProviderError):
            raise step
        return step


def hit(
    company: str,
    title: str,
    *,
    url: str | None = None,
    provider: str = "fake",
    location: str | None = "Bengaluru",
    description: str | None = "Python, FastAPI and PostgreSQL on AWS.",
    **extra: Any,
) -> JobHit:
    slug = f"{company}-{title}".lower().replace(" ", "-")
    return JobHit(
        provider=provider,
        external_id=slug,
        title=title,
        company=company,
        url=url or f"https://careers.{company.lower()}.example/jobs/{slug}",
        location=location,
        description=description,
        **extra,
    )


class FakeChecker:
    def __init__(self, verdict: str = "active") -> None:
        self.verdict = verdict
        self.checked: list[str] = []

    def check(self, url: str) -> str:
        self.checked.append(url)
        return self.verdict

    def check_many(self, urls: list[str], *, budget_seconds: float = 6.0) -> dict[str, str]:
        return {u: self.check(u) for u in urls}
