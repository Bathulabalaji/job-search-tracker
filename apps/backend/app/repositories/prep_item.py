from sqlalchemy import select

from app.models.enums import PrepCategory, PrepStatus
from app.models.prep_item import PrepItem
from app.repositories.base import BaseRepository


class PrepItemRepository(BaseRepository[PrepItem]):
    model = PrepItem

    def list(
        self,
        *,
        category: PrepCategory | None,
        status: PrepStatus | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> list[PrepItem]:
        stmt = select(PrepItem)
        if category is not None:
            stmt = stmt.where(PrepItem.category == category)
        if status is not None:
            stmt = stmt.where(PrepItem.status == status)
        if q:
            stmt = stmt.where(PrepItem.topic.ilike(f"%{q}%"))
        stmt = stmt.order_by(PrepItem.category, PrepItem.id).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))
