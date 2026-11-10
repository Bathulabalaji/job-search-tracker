from datetime import date

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ConflictError, NotFoundError
from app.models.daily_log import DailyLog
from app.repositories.daily_log import DailyLogRepository
from app.schemas.daily_log import DailyLogCreate, DailyLogUpdate, StreakRead
from app.services.analytics_math import compute_streaks
from app.services.common import apply_patch


class DailyLogService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.logs = DailyLogRepository(session)

    def list(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DailyLog]:
        return self.logs.list(date_from=date_from, date_to=date_to, limit=limit, offset=offset)

    def get(self, log_id: int) -> DailyLog:
        log = self.logs.get(log_id)
        if log is None:
            raise NotFoundError("Daily log", log_id)
        return log

    def create(self, data: DailyLogCreate) -> DailyLog:
        values = data.model_dump()
        values["log_date"] = data.log_date or self.clock.today()
        if self.logs.get_by_date(values["log_date"]) is not None:
            raise ConflictError(f"A log for {values['log_date']} already exists; update it instead")
        log = self.logs.add(DailyLog(**values))
        self.session.commit()
        self.session.refresh(log)
        return log

    def update(self, log_id: int, data: DailyLogUpdate) -> DailyLog:
        log = self.get(log_id)
        apply_patch(log, data)
        self.session.commit()
        self.session.refresh(log)
        return log

    def delete(self, log_id: int) -> None:
        self.logs.delete(self.get(log_id))
        self.session.commit()

    def streak(self) -> StreakRead:
        """Consecutive days with any recorded activity. See compute_streaks for the grace rule."""
        active = self.logs.active_dates()
        today = self.clock.today()
        current, longest = compute_streaks(active, today)
        return StreakRead(
            today=today,
            current=current,
            longest=longest,
            logged_today=today in active,
            last_active_date=max(active, default=None),
        )
