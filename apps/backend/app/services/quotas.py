"""Every per-user allowance in one place, so the app can show them and tests can check them.

The limits themselves are enforced where the work happens (each service consumes its bucket
from the shared RateLimiter); this module only reads them. A bucket's window is a rolling
24 hours, so `resets_at` is when the oldest counted use ages out.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.repositories.user import RateLimitRepository

DAY = timedelta(days=1)


@dataclass(frozen=True)
class Bucket:
    name: str  # what clients see: "messages", "searches", ...
    key: str  # the RateLimiter bucket
    label: str
    limit: int
    # Only offered when the feature behind it is configured on this server.
    enabled: bool


def buckets(settings: Settings, user_id: int) -> list[Bucket]:
    return [
        Bucket(
            "messages",
            f"chat:day:{user_id}",
            "Assistant messages",
            settings.chat_daily_messages,
            settings.llm_enabled,
        ),
        Bucket(
            "searches",
            f"job-search:{user_id}",
            "Job searches",
            settings.chat_search_daily_limit,
            settings.job_search_enabled,
        ),
        Bucket(
            "matches",
            f"match:{user_id}",
            "Resume comparisons",
            settings.match_daily_limit,
            settings.llm_enabled,
        ),
        Bucket(
            "recommendations",
            f"recommendations:{user_id}",
            "Jobs for you refreshes",
            settings.recommendations_refresh_per_day,
            settings.llm_enabled and settings.job_search_enabled,
        ),
        Bucket(
            "reindex",
            f"resume-process:{user_id}",
            "Resume re-indexing",
            settings.resume_process_daily_limit,
            settings.llm_enabled,
        ),
    ]


@dataclass(frozen=True)
class QuotaUsage:
    name: str
    label: str
    limit: int
    used: int
    resets_at: datetime | None  # None: nothing used, nothing to wait for


def usage(session: Session, clock: Clock, settings: Settings, user_id: int) -> list[QuotaUsage]:
    repo = RateLimitRepository(session)
    now = clock.now()
    rows: list[QuotaUsage] = []
    for bucket in buckets(settings, user_id):
        if not bucket.enabled:
            continue
        used, oldest = repo.window_stats(bucket.key, now - DAY)
        rows.append(
            QuotaUsage(
                name=bucket.name,
                label=bucket.label,
                limit=bucket.limit,
                used=used,
                resets_at=(oldest + DAY) if oldest is not None else None,
            )
        )
    return rows
