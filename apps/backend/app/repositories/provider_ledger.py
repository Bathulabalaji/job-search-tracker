"""State about external AI providers. Global on purpose: budgets belong to the deployment, not
to a user, so nothing here filters by user_id (see tests/unit/test_repository_scoping.py)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.provider_ledger import ProviderResourceState, ProviderUsageEvent


@dataclass(frozen=True)
class UsageRow:
    provider: str
    resource: str
    task: str
    outcome: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: int


class ProviderLedgerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock(self, resource: str, provider: str) -> ProviderResourceState:
        """The state row for `resource`, locked until the caller commits.

        The row is created on first use. INSERT ... ON CONFLICT DO NOTHING means two workers
        meeting a brand-new model at the same moment both end up locking the same row.
        """
        self.session.execute(
            pg_insert(ProviderResourceState)
            .values(resource=resource, provider=provider)
            .on_conflict_do_nothing(index_elements=["resource"])
        )
        return self.session.execute(
            select(ProviderResourceState)
            .where(ProviderResourceState.resource == resource)
            .with_for_update()
        ).scalar_one()

    def get(self, resource: str) -> ProviderResourceState | None:
        return self.session.get(ProviderResourceState, resource)

    def list_states(self) -> list[ProviderResourceState]:
        stmt = select(ProviderResourceState).order_by(
            ProviderResourceState.provider, ProviderResourceState.resource
        )
        return list(self.session.scalars(stmt))

    def add_event(self, event: ProviderUsageEvent) -> None:
        self.session.add(event)
        self.session.flush()

    def usage_summary(self, since: datetime) -> list[UsageRow]:
        stmt = (
            select(
                ProviderUsageEvent.provider,
                ProviderUsageEvent.resource,
                ProviderUsageEvent.task,
                ProviderUsageEvent.outcome,
                func.count(),
                func.coalesce(func.sum(ProviderUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(ProviderUsageEvent.completion_tokens), 0),
                func.coalesce(func.avg(ProviderUsageEvent.latency_ms), 0),
            )
            .where(ProviderUsageEvent.created_at >= since)
            .group_by(
                ProviderUsageEvent.provider,
                ProviderUsageEvent.resource,
                ProviderUsageEvent.task,
                ProviderUsageEvent.outcome,
            )
            .order_by(ProviderUsageEvent.provider, ProviderUsageEvent.resource)
        )
        return [
            UsageRow(
                provider=row[0],
                resource=row[1],
                task=row[2],
                outcome=row[3],
                calls=int(row[4]),
                prompt_tokens=int(row[5]),
                completion_tokens=int(row[6]),
                avg_latency_ms=int(row[7]),
            )
            for row in self.session.execute(stmt)
        ]

    def purge_events_before(self, cutoff: datetime) -> int:
        return int(
            self.session.query(ProviderUsageEvent)
            .filter(ProviderUsageEvent.created_at < cutoff)
            .delete()
        )
