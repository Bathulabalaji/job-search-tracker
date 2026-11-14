"""The shared cache of job postings. Global on purpose: a posting is public data fetched from
a search API and belongs to no user, so nothing here filters by user_id (see
tests/unit/test_repository_scoping.py). Who searched for what lives in job_search_queries."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.job_posting import JobPosting


class JobPostingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, posting_id: int) -> JobPosting | None:
        return self.session.get(JobPosting, posting_id)

    def get_many(self, ids: Sequence[int]) -> list[JobPosting]:
        if not ids:
            return []
        rows = {
            p.id: p for p in self.session.scalars(select(JobPosting).where(JobPosting.id.in_(ids)))
        }
        return [rows[i] for i in ids if i in rows]

    def find(self, canonical_url: str, fingerprint: str) -> JobPosting | None:
        stmt = (
            select(JobPosting)
            .where(
                or_(
                    JobPosting.canonical_url == canonical_url, JobPosting.fingerprint == fingerprint
                )
            )
            .order_by((JobPosting.canonical_url == canonical_url).desc(), JobPosting.id.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def add(self, posting: JobPosting) -> JobPosting:
        self.session.add(posting)
        self.session.flush()
        return posting

    def search_cached(self, words: Sequence[str], now: datetime, limit: int) -> list[JobPosting]:
        """Unexpired postings whose title or company mentions every word. Used when every
        provider is out of quota, so the user still gets something recent."""
        stmt = select(JobPosting).where(JobPosting.expires_at > now)
        for word in words:
            pattern = f"%{word}%"
            stmt = stmt.where(
                or_(JobPosting.title.ilike(pattern), JobPosting.company.ilike(pattern))
            )
        stmt = stmt.order_by(JobPosting.posted_at.desc().nulls_last(), JobPosting.id.desc())
        return list(self.session.scalars(stmt.limit(limit)))

    def delete_expired(self, before: datetime) -> int:
        """Housekeeping: postings no opportunity points at, past their cache life."""
        from app.models.opportunity import Opportunity

        linked = select(Opportunity.job_posting_id).where(
            Opportunity.job_posting_id.is_not(None), Opportunity.user_id.is_not(None)
        )
        rows = self.session.scalars(
            select(JobPosting).where(JobPosting.expires_at < before, JobPosting.id.not_in(linked))
        ).all()
        for row in rows:
            self.session.delete(row)
        self.session.flush()
        return len(rows)
