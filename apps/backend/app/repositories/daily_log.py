from datetime import date

from sqlalchemy import or_, select

from app.models.daily_log import DailyLog
from app.repositories.base import BaseRepository


class DailyLogRepository(BaseRepository[DailyLog]):
    model = DailyLog

    def get_by_date(self, log_date: date) -> DailyLog | None:
        return self.session.scalar(select(DailyLog).where(DailyLog.log_date == log_date))

    def between(self, start: date, end: date) -> list[DailyLog]:
        stmt = (
            select(DailyLog)
            .where(DailyLog.log_date >= start)
            .where(DailyLog.log_date <= end)
            .order_by(DailyLog.log_date)
        )
        return list(self.session.scalars(stmt))

    def list(
        self, *, date_from: date | None, date_to: date | None, limit: int, offset: int
    ) -> list[DailyLog]:
        stmt = select(DailyLog)
        if date_from is not None:
            stmt = stmt.where(DailyLog.log_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(DailyLog.log_date <= date_to)
        stmt = stmt.order_by(DailyLog.log_date.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def active_dates(self) -> set[date]:
        """Days with any recorded activity (a log full of zeros does not extend a streak)."""
        counts = (
            DailyLog.applications_sent
            + DailyLog.messages_sent
            + DailyLog.referrals_requested
            + DailyLog.problems_solved
            + DailyLog.mocks_done
        )
        stmt = select(DailyLog.log_date).where(or_(counts > 0, DailyLog.hours_prep > 0))
        return set(self.session.scalars(stmt))
