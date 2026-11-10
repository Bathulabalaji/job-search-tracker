from sqlalchemy import or_, select

from app.models.resume import Resume
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    model = Resume

    def list(self, *, q: str | None, limit: int, offset: int) -> list[Resume]:
        stmt = select(Resume)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Resume.label.ilike(like), Resume.focus.ilike(like), Resume.file_name.ilike(like)
                )
            )
        stmt = stmt.order_by(Resume.label, Resume.id).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))
