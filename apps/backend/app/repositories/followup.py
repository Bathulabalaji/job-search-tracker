from datetime import date

from sqlalchemy import select

from app.models.enums import FollowupStatus
from app.models.followup import Followup
from app.repositories.base import BaseRepository


class FollowupRepository(BaseRepository[Followup]):
    model = Followup

    def has_pending(self, opportunity_id: int) -> bool:
        stmt = (
            select(Followup.id)
            .where(Followup.opportunity_id == opportunity_id)
            .where(Followup.status == FollowupStatus.pending)
            .limit(1)
        )
        return self.session.scalar(stmt) is not None

    def list(
        self,
        *,
        opportunity_id: int | None,
        status: FollowupStatus | None,
        due_on_or_before: date | None,
        limit: int,
        offset: int,
    ) -> list[Followup]:
        stmt = select(Followup)
        if opportunity_id is not None:
            stmt = stmt.where(Followup.opportunity_id == opportunity_id)
        if status is not None:
            stmt = stmt.where(Followup.status == status)
        if due_on_or_before is not None:
            stmt = stmt.where(Followup.due_date <= due_on_or_before)
        stmt = stmt.order_by(Followup.due_date, Followup.id).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))
