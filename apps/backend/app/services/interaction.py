from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import InvalidInputError, NotFoundError
from app.models.interaction import Interaction
from app.repositories.contact import ContactRepository
from app.repositories.interaction import InteractionRepository
from app.repositories.opportunity import OpportunityRepository
from app.schemas.interaction import InteractionCreate, InteractionUpdate
from app.services.common import apply_patch

# A little slack so a phone whose clock is a minute fast can still log "just now".
FUTURE_SLACK = timedelta(minutes=5)


class InteractionService:
    def __init__(self, session: Session, clock: Clock, user_id: int) -> None:
        self.session = session
        self.clock = clock
        self.interactions = InteractionRepository(session, user_id)
        self.opportunities = OpportunityRepository(session, user_id)
        self.contacts = ContactRepository(session, user_id)

    def list(
        self,
        *,
        opportunity_id: int | None = None,
        contact_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interaction]:
        return self.interactions.list(
            opportunity_id=opportunity_id, contact_id=contact_id, limit=limit, offset=offset
        )

    def get(self, interaction_id: int) -> Interaction:
        interaction = self.interactions.get(interaction_id)
        if interaction is None:
            raise NotFoundError("Interaction", interaction_id)
        return interaction

    def create(self, data: InteractionCreate) -> Interaction:
        if self.opportunities.get(data.opportunity_id) is None:
            raise NotFoundError("Opportunity", data.opportunity_id)
        self._require_contact(data.contact_id)
        self._require_not_future(data.occurred_at)
        values = data.model_dump()
        values["occurred_at"] = data.occurred_at or self.clock.now()
        interaction = self.interactions.add(Interaction(**values))
        self.session.commit()
        self.session.refresh(interaction)
        return interaction

    def update(self, interaction_id: int, data: InteractionUpdate) -> Interaction:
        interaction = self.get(interaction_id)
        if "contact_id" in data.model_fields_set:
            self._require_contact(data.contact_id)
        if "occurred_at" in data.model_fields_set:
            self._require_not_future(data.occurred_at)
        apply_patch(interaction, data)
        self.session.commit()
        self.session.refresh(interaction)
        return interaction

    def delete(self, interaction_id: int) -> None:
        self.interactions.delete(self.get(interaction_id))
        self.session.commit()

    def _require_contact(self, contact_id: int | None) -> None:
        if contact_id is not None and self.contacts.get(contact_id) is None:
            raise NotFoundError("Contact", contact_id)

    def _require_not_future(self, when: datetime | None) -> None:
        if when is None:
            return
        if when.tzinfo is None:
            when = when.replace(tzinfo=self.clock.tz)
        if when > self.clock.now() + FUTURE_SLACK:
            raise InvalidInputError("The date can't be in the future")
