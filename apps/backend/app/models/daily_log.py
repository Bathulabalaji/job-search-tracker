from datetime import date

from sqlalchemy import CheckConstraint, Date, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class DailyLog(OwnedMixin, Base):
    __tablename__ = "daily_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date"),
        CheckConstraint(
            "applications_sent >= 0 AND messages_sent >= 0 AND referrals_requested >= 0 "
            "AND problems_solved >= 0 AND mocks_done >= 0",
            name="counts_non_negative",
        ),
        CheckConstraint("hours_prep >= 0 AND hours_prep <= 24", name="hours_prep_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    log_date: Mapped[date] = mapped_column(Date)
    applications_sent: Mapped[int] = mapped_column(default=0, server_default="0")
    messages_sent: Mapped[int] = mapped_column(default=0, server_default="0")
    referrals_requested: Mapped[int] = mapped_column(default=0, server_default="0")
    problems_solved: Mapped[int] = mapped_column(default=0, server_default="0")
    mocks_done: Mapped[int] = mapped_column(default=0, server_default="0")
    hours_prep: Mapped[float] = mapped_column(default=0.0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
