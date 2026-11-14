from datetime import datetime

from sqlalchemy import select

from app.models.job_posting import JobSearchQuery
from app.models.opportunity import Opportunity
from app.repositories.base import BaseRepository


class JobSearchQueryRepository(BaseRepository[JobSearchQuery]):
    model = JobSearchQuery

    def recent(self, cache_key: str, since: datetime) -> JobSearchQuery | None:
        stmt = (
            select(JobSearchQuery)
            .where(
                JobSearchQuery.user_id == self.user_id,
                JobSearchQuery.cache_key == cache_key,
                JobSearchQuery.created_at >= since,
            )
            .order_by(JobSearchQuery.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def tracked(self, posting_ids: list[int]) -> dict[int, int]:
        """posting id -> this user's opportunity id, for postings already in the pipeline."""
        if not posting_ids:
            return {}
        stmt = select(Opportunity.job_posting_id, Opportunity.id).where(
            Opportunity.user_id == self.user_id, Opportunity.job_posting_id.in_(posting_ids)
        )
        return {int(pid): int(oid) for pid, oid in self.session.execute(stmt) if pid is not None}
