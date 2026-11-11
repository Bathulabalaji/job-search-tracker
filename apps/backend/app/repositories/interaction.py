from sqlalchemy import select

from app.models.interaction import Interaction
from app.repositories.base import BaseRepository


class InteractionRepository(BaseRepository[Interaction]):
    model = Interaction

    def list(
        self, *, opportunity_id: int | None, contact_id: int | None, limit: int, offset: int
    ) -> list[Interaction]:
        stmt = select(Interaction).where(Interaction.user_id == self.user_id)
        if opportunity_id is not None:
            stmt = stmt.where(Interaction.opportunity_id == opportunity_id)
        if contact_id is not None:
            stmt = stmt.where(Interaction.contact_id == contact_id)
        stmt = stmt.order_by(Interaction.occurred_at.desc(), Interaction.id.desc())
        return list(self.session.scalars(stmt.limit(limit).offset(offset)))
