from datetime import date

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import NotFoundError
from app.models.enums import FollowupStatus
from app.models.followup import Followup
from app.repositories.followup import FollowupRepository
from app.repositories.opportunity import OpportunityRepository
from app.schemas.followup import FollowupCreate, FollowupUpdate
from app.services.common import apply_patch


class FollowupService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.followups = FollowupRepository(session)
        self.opportunities = OpportunityRepository(session)

    def list(
        self,
        *,
        opportunity_id: int | None = None,
        status: FollowupStatus | None = None,
        due_on_or_before: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Followup]:
        return self.followups.list(
            opportunity_id=opportunity_id,
            status=status,
            due_on_or_before=due_on_or_before,
            limit=limit,
            offset=offset,
        )

    def get(self, followup_id: int) -> Followup:
        followup = self.followups.get(followup_id)
        if followup is None:
            raise NotFoundError("Followup", followup_id)
        return followup

    def create(self, data: FollowupCreate) -> Followup:
        if self.opportunities.get(data.opportunity_id) is None:
            raise NotFoundError("Opportunity", data.opportunity_id)
        followup = self.followups.add(Followup(**data.model_dump()))
        self.session.commit()
        self.session.refresh(followup)
        return followup

    def update(self, followup_id: int, data: FollowupUpdate) -> Followup:
        followup = self.get(followup_id)
        apply_patch(followup, data)
        if "status" in data.model_fields_set:
            # done_at is derived from status so clients cannot put it out of step.
            followup.done_at = self.clock.now() if followup.status == FollowupStatus.done else None
        self.session.commit()
        self.session.refresh(followup)
        return followup

    def delete(self, followup_id: int) -> None:
        self.followups.delete(self.get(followup_id))
        self.session.commit()
