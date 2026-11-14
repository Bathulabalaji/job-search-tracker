"""Phase 4: how well each resume fits a job, and the "Jobs for you" feed."""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class JobMatch(OwnedMixin, Base):
    """One resume scored against one job (an opportunity's JD or a searched posting).

    Cached by the hash of the JD text and of the resume file: change either and the row no
    longer matches, so the next request recomputes instead of serving a stale score.
    """

    __tablename__ = "job_matches"
    __table_args__ = (
        CheckConstraint(
            "(opportunity_id IS NOT NULL) <> (job_posting_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        Index("ix_job_matches_opportunity", "user_id", "opportunity_id"),
        Index("ix_job_matches_posting", "user_id", "job_posting_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE")
    )
    job_posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE")
    )
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    jd_hash: Mapped[str] = mapped_column(String(40))
    resume_hash: Mapped[str] = mapped_column(String(64))
    vector_score: Mapped[float | None] = mapped_column(Float)  # mean cosine of the top passages
    llm_score: Mapped[int | None]  # 0-100
    matched_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobSearchProfile(OwnedMixin, Base):
    """What "Jobs for you" searches for. One per user; starts from their resumes' profiles."""

    __tablename__ = "job_search_profiles"
    __table_args__ = (Index("uq_job_search_profiles_user", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default="{}"
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default="{}"
    )
    work_modes: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), default=list, server_default="{}"
    )
    min_vector_score: Mapped[float] = mapped_column(Float, default=0.55, server_default="0.55")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    derived_from_resume_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, server_default="{}"
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRecommendation(OwnedMixin, Base):
    """A posting worth a look, ranked by embedding similarity to the user's resumes."""

    __tablename__ = "job_recommendations"
    __table_args__ = (
        Index("uq_job_recommendations_user_posting", "user_id", "job_posting_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    best_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL")
    )
    vector_score: Mapped[float] = mapped_column(Float)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
