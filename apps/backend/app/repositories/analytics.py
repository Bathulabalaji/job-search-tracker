from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import Direction, InteractionType, Stage
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity
from app.services.analytics_math import OpportunityProgress


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def opportunity_progress(self) -> list[OpportunityProgress]:
        opportunities = self.session.execute(
            select(Opportunity.id, Opportunity.source, Opportunity.stage)
        ).all()

        visited: dict[int, set[Stage]] = {}
        moves = self.session.execute(
            select(Interaction.opportunity_id, Interaction.from_stage, Interaction.to_stage).where(
                Interaction.type == InteractionType.stage_change
            )
        ).all()
        for opportunity_id, from_stage, to_stage in moves:
            stages = visited.setdefault(opportunity_id, set())
            if from_stage is not None:
                stages.add(from_stage)
            if to_stage is not None:
                stages.add(to_stage)

        responded = set(
            self.session.scalars(
                select(Interaction.opportunity_id)
                .where(Interaction.direction == Direction.in_)
                .where(Interaction.type != InteractionType.stage_change)
                .distinct()
            )
        )
        return [
            OpportunityProgress(
                source=source,
                visited=frozenset(visited.get(opp_id, set()) | {stage}),
                responded=opp_id in responded,
            )
            for opp_id, source, stage in opportunities
        ]

    def interview_times(self, start: datetime, end: datetime) -> list[datetime]:
        stmt = (
            select(Interaction.occurred_at)
            .where(Interaction.type == InteractionType.interview)
            .where(Interaction.occurred_at >= start)
            .where(Interaction.occurred_at < end)
        )
        return list(self.session.scalars(stmt))

    def stage_counts(self) -> dict[Stage, int]:
        rows = self.session.execute(
            select(Opportunity.stage, func.count()).group_by(Opportunity.stage)
        ).all()
        return {stage: count for stage, count in rows}
