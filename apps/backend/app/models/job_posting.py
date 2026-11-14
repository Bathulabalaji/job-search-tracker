from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class JobPosting(Base):
    """A posting fetched from a job-search API. A shared cache, not user data: two users who
    search for the same role see the same row, and nothing here says who searched for it."""

    __tablename__ = "job_postings"
    __table_args__ = (
        Index("uq_job_postings_canonical_url", "canonical_url", unique=True),
        Index("ix_job_postings_fingerprint", "fingerprint"),
        Index("ix_job_postings_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))  # adzuna | jsearch | serpapi | tavily
    external_id: Mapped[str] = mapped_column(String(200))
    canonical_url: Mapped[str] = mapped_column(String(1000))
    # sha1 of normalised company|title|location: the same job reached through two links.
    fingerprint: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2))
    work_mode: Mapped[str | None] = mapped_column(String(16))  # remote | hybrid | onsite
    # Where the apply link points: linkedin | naukri | indeed | company | other
    source_site: Mapped[str] = mapped_column(String(16), default="other", server_default="other")
    apply_url: Mapped[str] = mapped_column(String(1000))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    salary_text: Mapped[str | None] = mapped_column(String(200))
    # Sanitised plain text, capped. Untrusted: shown to the model only inside a data wrapper.
    description: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    active_status: Mapped[str] = mapped_column(
        String(16), default="unknown", server_default="unknown"
    )  # unknown | active | inactive
    active_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobSearchQuery(OwnedMixin, Base):
    """One search a user ran: answers an identical repeat from the cache, and later feeds
    recommendations."""

    __tablename__ = "job_search_queries"
    __table_args__ = (Index("ix_job_search_queries_user_key", "user_id", "cache_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(40))
    query_text: Mapped[str] = mapped_column(String(300))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    providers_used: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default="{}"
    )
    result_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    notices: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
