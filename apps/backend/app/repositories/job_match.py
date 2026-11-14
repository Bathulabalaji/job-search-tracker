from sqlalchemy import delete, select

from app.models.job_match import JobMatch, JobRecommendation, JobSearchProfile
from app.models.job_posting import JobPosting
from app.repositories.base import BaseRepository


class JobMatchRepository(BaseRepository[JobMatch]):
    model = JobMatch

    def for_target(
        self, *, opportunity_id: int | None = None, job_posting_id: int | None = None
    ) -> list[JobMatch]:
        stmt = select(JobMatch).where(JobMatch.user_id == self.user_id)
        if opportunity_id is not None:
            stmt = stmt.where(JobMatch.opportunity_id == opportunity_id)
        else:
            stmt = stmt.where(JobMatch.job_posting_id == job_posting_id)
        return list(self.session.scalars(stmt.order_by(JobMatch.created_at.desc())))

    def clear(
        self,
        resume_ids: list[int],
        *,
        opportunity_id: int | None = None,
        job_posting_id: int | None = None,
    ) -> None:
        stmt = delete(JobMatch).where(
            JobMatch.user_id == self.user_id, JobMatch.resume_id.in_(resume_ids)
        )
        if opportunity_id is not None:
            stmt = stmt.where(JobMatch.opportunity_id == opportunity_id)
        else:
            stmt = stmt.where(JobMatch.job_posting_id == job_posting_id)
        self.session.execute(stmt)


class JobSearchProfileRepository(BaseRepository[JobSearchProfile]):
    model = JobSearchProfile

    def mine(self) -> JobSearchProfile | None:
        stmt = select(JobSearchProfile).where(JobSearchProfile.user_id == self.user_id)
        return self.session.scalars(stmt).first()


class JobRecommendationRepository(BaseRepository[JobRecommendation]):
    model = JobRecommendation

    def existing_posting_ids(self) -> set[int]:
        """Every posting already recommended (dismissed ones too: they must not come back)."""
        stmt = select(JobRecommendation.job_posting_id).where(
            JobRecommendation.user_id == self.user_id
        )
        return {int(i) for i in self.session.scalars(stmt)}

    def visible(self, limit: int) -> list[tuple[JobRecommendation, JobPosting]]:
        stmt = (
            select(JobRecommendation, JobPosting)
            .join(JobPosting, JobPosting.id == JobRecommendation.job_posting_id)
            .where(
                JobRecommendation.user_id == self.user_id, JobRecommendation.dismissed.is_(False)
            )
            .order_by(JobRecommendation.vector_score.desc(), JobRecommendation.id.desc())
            .limit(limit)
        )
        return [(r, p) for r, p in self.session.execute(stmt)]
