from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.resume import Resume
from app.repositories.resume import ResumeRepository
from app.schemas.resume import ResumeCreate, ResumeUpdate
from app.services.common import apply_patch


class ResumeService:
    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.resumes = ResumeRepository(session, user_id)

    def list(self, *, q: str | None = None, limit: int = 100, offset: int = 0) -> list[Resume]:
        return self.resumes.list(q=q, limit=limit, offset=offset)

    def get(self, resume_id: int) -> Resume:
        resume = self.resumes.get(resume_id)
        if resume is None:
            raise NotFoundError("Resume", resume_id)
        return resume

    def create(self, data: ResumeCreate) -> Resume:
        resume = self.resumes.add(Resume(**data.model_dump()))
        self.session.commit()
        self.session.refresh(resume)
        return resume

    def update(self, resume_id: int, data: ResumeUpdate) -> Resume:
        resume = self.get(resume_id)
        apply_patch(resume, data)
        self.session.commit()
        self.session.refresh(resume)
        return resume

    def delete(self, resume_id: int) -> None:
        self.resumes.delete(self.get(resume_id))
        self.session.commit()
