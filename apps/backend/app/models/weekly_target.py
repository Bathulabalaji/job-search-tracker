from datetime import date

from sqlalchemy import CheckConstraint, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class WeeklyTarget(OwnedMixin, Base):
    __tablename__ = "weekly_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start"),
        CheckConstraint(
            "applications >= 0 AND messages >= 0 AND referrals >= 0 "
            "AND problems >= 0 AND mocks >= 0 AND interviews >= 0",
            name="counts_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[date] = mapped_column(Date)  # always a Monday
    applications: Mapped[int] = mapped_column(default=0, server_default="0")
    messages: Mapped[int] = mapped_column(default=0, server_default="0")
    referrals: Mapped[int] = mapped_column(default=0, server_default="0")
    problems: Mapped[int] = mapped_column(default=0, server_default="0")
    mocks: Mapped[int] = mapped_column(default=0, server_default="0")
    interviews: Mapped[int] = mapped_column(default=0, server_default="0")
