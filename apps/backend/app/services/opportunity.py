from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import (
    Direction,
    FollowupChannel,
    InteractionType,
    Source,
    Stage,
)
from app.models.followup import Followup
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity
from app.repositories.followup import FollowupRepository
from app.repositories.interaction import InteractionRepository
from app.repositories.opportunity import OpportunityRepository
from app.schemas.followup import FollowupRead
from app.schemas.interaction import InteractionRead
from app.schemas.opportunity import (
    MoveRequest,
    MoveResponse,
    OpportunityCreate,
    OpportunityRead,
    OpportunityUpdate,
)
from app.services import rules
from app.services.common import apply_patch


class OpportunityService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, user_id: int) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.opportunities = OpportunityRepository(session, user_id)
        self.interactions = InteractionRepository(session, user_id)
        self.followups = FollowupRepository(session, user_id)

    # ---- reads -------------------------------------------------------------------------------

    def list(
        self,
        *,
        stage: Stage | None = None,
        priority: int | None = None,
        source: Source | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OpportunityRead]:
        rows = self.opportunities.list(
            stage=stage, priority=priority, source=source, q=q, limit=limit, offset=offset
        )
        return [self._to_read(opp, last_contact) for opp, last_contact in rows]

    def get(self, opportunity_id: int) -> OpportunityRead:
        return self._read_by_id(opportunity_id)

    # ---- writes ------------------------------------------------------------------------------

    def create(self, data: OpportunityCreate) -> OpportunityRead:
        opp = self.opportunities.add(Opportunity(**data.model_dump()))
        self._ensure_auto_followup(opp)
        self.session.commit()
        return self._read_by_id(opp.id)

    def update(self, opportunity_id: int, data: OpportunityUpdate) -> OpportunityRead:
        opp = self._get_or_404(opportunity_id)
        apply_patch(opp, data)
        self.session.commit()
        return self._read_by_id(opportunity_id)

    def delete(self, opportunity_id: int) -> None:
        opp = self._get_or_404(opportunity_id)
        self.opportunities.delete(opp)
        self.session.commit()

    def move(self, opportunity_id: int, data: MoveRequest) -> MoveResponse:
        opp = self._get_or_404(opportunity_id)
        old_stage, new_stage = opp.stage, data.stage
        if old_stage == new_stage:
            raise ConflictError(f"Opportunity {opportunity_id} is already in stage '{new_stage}'")

        opp.stage = new_stage
        summary = f"Stage: {old_stage} → {new_stage}"
        if data.note:
            summary = f"{summary}. {data.note}"
        interaction = self.interactions.add(
            Interaction(
                opportunity_id=opp.id,
                type=InteractionType.stage_change,
                from_stage=old_stage,
                to_stage=new_stage,
                direction=Direction.out,
                summary=summary,
                occurred_at=self.clock.now(),
            )
        )
        followup = self._ensure_auto_followup(opp)
        self.session.commit()

        return MoveResponse(
            opportunity=self._read_by_id(opportunity_id),
            interaction=InteractionRead.model_validate(interaction),
            followup_created=FollowupRead.model_validate(followup) if followup else None,
        )

    # ---- internals ---------------------------------------------------------------------------

    def _ensure_auto_followup(self, opp: Opportunity) -> Followup | None:
        """Auto-rule: entering 'applied'/'screening' schedules a follow-up in N working days.

        Skipped when the opportunity already has a pending follow-up, so hopping
        applied -> screening does not pile up duplicates.
        """
        if opp.stage not in rules.AUTO_FOLLOWUP_STAGES:
            return None
        if self.followups.has_pending(opp.id):
            return None
        due = rules.add_working_days(self.clock.today(), self.settings.followup_working_days)
        return self.followups.add(
            Followup(
                opportunity_id=opp.id,
                due_date=due,
                channel=FollowupChannel.email,
                message_draft=None,
            )
        )

    def _get_or_404(self, opportunity_id: int) -> Opportunity:
        opp = self.opportunities.get(opportunity_id)
        if opp is None:
            raise NotFoundError("Opportunity", opportunity_id)
        return opp

    def _read_by_id(self, opportunity_id: int) -> OpportunityRead:
        row = self.opportunities.get_with_last_contact(opportunity_id)
        if row is None:
            raise NotFoundError("Opportunity", opportunity_id)
        opp, last_contact = row
        self.session.refresh(opp)
        return self._to_read(opp, last_contact)

    def _to_read(self, opp: Opportunity, last_contact_at: datetime | None) -> OpportunityRead:
        """Days since contact counts from the last real interaction, else from creation."""
        now = self.clock.now()
        days = rules.days_since(last_contact_at or opp.created_at, now)
        read = OpportunityRead.model_validate(opp)
        return read.model_copy(
            update={
                "last_contact_at": last_contact_at,
                "days_since_contact": days,
                "ghosted_suggestion": rules.is_ghost_suggested(
                    opp.stage, days, self.settings.ghost_after_days
                ),
            }
        )
