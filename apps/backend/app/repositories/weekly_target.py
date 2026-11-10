from datetime import date

from sqlalchemy import select

from app.models.weekly_target import WeeklyTarget
from app.repositories.base import BaseRepository


class WeeklyTargetRepository(BaseRepository[WeeklyTarget]):
    model = WeeklyTarget

    def get_by_week(self, week_start: date) -> WeeklyTarget | None:
        return self.session.scalar(
            select(WeeklyTarget).where(WeeklyTarget.week_start == week_start)
        )

    def latest_on_or_before(self, week_start: date) -> WeeklyTarget | None:
        stmt = (
            select(WeeklyTarget)
            .where(WeeklyTarget.week_start <= week_start)
            .order_by(WeeklyTarget.week_start.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list(self, *, limit: int, offset: int) -> list[WeeklyTarget]:
        stmt = select(WeeklyTarget).order_by(WeeklyTarget.week_start.desc())
        return list(self.session.scalars(stmt.limit(limit).offset(offset)))
