from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.weekly_target import WeeklyTarget
from app.repositories.weekly_target import WeeklyTargetRepository
from app.schemas.weekly_target import WeeklyTargetCreate, WeeklyTargetUpdate
from app.services.common import apply_patch


class WeeklyTargetService:
    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.targets = WeeklyTargetRepository(session, user_id)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[WeeklyTarget]:
        return self.targets.list(limit=limit, offset=offset)

    def get(self, target_id: int) -> WeeklyTarget:
        target = self.targets.get(target_id)
        if target is None:
            raise NotFoundError("Weekly target", target_id)
        return target

    def create(self, data: WeeklyTargetCreate) -> WeeklyTarget:
        if self.targets.get_by_week(data.week_start) is not None:
            raise ConflictError(f"Targets for the week of {data.week_start} already exist")
        target = self.targets.add(WeeklyTarget(**data.model_dump()))
        self.session.commit()
        self.session.refresh(target)
        return target

    def update(self, target_id: int, data: WeeklyTargetUpdate) -> WeeklyTarget:
        target = self.get(target_id)
        apply_patch(target, data)
        self.session.commit()
        self.session.refresh(target)
        return target

    def delete(self, target_id: int) -> None:
        self.targets.delete(self.get(target_id))
        self.session.commit()
