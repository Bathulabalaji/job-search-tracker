from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select

from app.models.enums import InteractionType, Source, Stage
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity
from app.repositories.base import BaseRepository


class OpportunityRepository(BaseRepository[Opportunity]):
    model = Opportunity

    def _with_last_contact(self) -> Select[Any]:
        last_contact = (
            select(
                Interaction.opportunity_id,
                func.max(Interaction.occurred_at).label("last_contact_at"),
            )
            .where(Interaction.type != InteractionType.stage_change)
            .group_by(Interaction.opportunity_id)
            .subquery()
        )
        return (
            select(Opportunity, last_contact.c.last_contact_at)
            .outerjoin(last_contact, last_contact.c.opportunity_id == Opportunity.id)
            .where(Opportunity.user_id == self.user_id)
        )

    def get_with_last_contact(
        self, opportunity_id: int
    ) -> tuple[Opportunity, datetime | None] | None:
        row = self.session.execute(
            self._with_last_contact().where(Opportunity.id == opportunity_id)
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    def list(
        self,
        *,
        stage: Stage | None,
        priority: int | None,
        source: Source | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> list[tuple[Opportunity, datetime | None]]:
        stmt = self._with_last_contact()
        if stage is not None:
            stmt = stmt.where(Opportunity.stage == stage)
        if priority is not None:
            stmt = stmt.where(Opportunity.priority == priority)
        if source is not None:
            stmt = stmt.where(Opportunity.source == source)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Opportunity.company.ilike(like), Opportunity.role.ilike(like)))
        stmt = stmt.order_by(Opportunity.updated_at.desc(), Opportunity.id.desc())
        rows = self.session.execute(stmt.limit(limit).offset(offset)).all()
        return [(row[0], row[1]) for row in rows]
