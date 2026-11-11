from datetime import date, datetime

from sqlalchemy import ARRAY, CheckConstraint, Date, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Source, Stage, WorkMode
from app.models.mixins import OwnedMixin
from app.models.types import enum_column


class Opportunity(OwnedMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 3", name="priority_range"),
        CheckConstraint("fit_score IS NULL OR fit_score BETWEEN 0 AND 100", name="fit_score_range"),
        Index("ix_opportunities_stage", "stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    source: Mapped[Source] = mapped_column(enum_column(Source), default=Source.other)
    stack_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    location: Mapped[str | None] = mapped_column(String(200))
    work_mode: Mapped[WorkMode | None] = mapped_column(enum_column(WorkMode))
    stage: Mapped[Stage] = mapped_column(enum_column(Stage), default=Stage.found)
    priority: Mapped[int] = mapped_column(default=2, server_default="2")
    fit_score: Mapped[int | None]
    jd_text: Mapped[str | None] = mapped_column(Text)
    jd_url: Mapped[str | None] = mapped_column(String(1000))
    expected_ctc_note: Mapped[str | None] = mapped_column(String(500))
    next_action: Mapped[str | None] = mapped_column(String(500))
    next_action_due: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
