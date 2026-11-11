from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FollowupStatus, InteractionType, Stage
from app.models.followup import Followup
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity


class DashboardRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    def due_followups(self, on_or_before: date) -> list[tuple[Followup, Opportunity]]:
        stmt = (
            select(Followup, Opportunity)
            .where(Followup.user_id == self.user_id)
            .join(Opportunity, Opportunity.id == Followup.opportunity_id)
            .where(Followup.status == FollowupStatus.pending)
            .where(Followup.due_date <= on_or_before)
            .order_by(Followup.due_date, Followup.id)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def interviews_between(
        self, start: datetime, end: datetime
    ) -> list[tuple[Interaction, Opportunity]]:
        stmt = (
            select(Interaction, Opportunity)
            .where(Interaction.user_id == self.user_id)
            .join(Opportunity, Opportunity.id == Interaction.opportunity_id)
            .where(Interaction.type == InteractionType.interview)
            .where(Interaction.occurred_at >= start)
            .where(Interaction.occurred_at < end)
            .order_by(Interaction.occurred_at, Interaction.id)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def open_with_next_action(self, closed: frozenset[Stage], limit: int) -> list[Opportunity]:
        stmt = (
            select(Opportunity)
            .where(Opportunity.user_id == self.user_id)
            .where(Opportunity.next_action.is_not(None))
            .where(Opportunity.next_action != "")
            .where(Opportunity.stage.not_in(closed))
            .order_by(
                Opportunity.next_action_due.asc().nulls_last(),
                Opportunity.priority,
                Opportunity.updated_at.desc(),
            )
            .limit(limit)
        )
        return list(self.session.scalars(stmt))
