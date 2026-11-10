from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.enums import PrepCategory, PrepStatus
from app.models.prep_item import PrepItem
from app.repositories.prep_item import PrepItemRepository
from app.schemas.prep_item import PrepItemCreate, PrepItemUpdate
from app.services.common import apply_patch


class PrepItemService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.items = PrepItemRepository(session)

    def list(
        self,
        *,
        category: PrepCategory | None = None,
        status: PrepStatus | None = None,
        q: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PrepItem]:
        return self.items.list(category=category, status=status, q=q, limit=limit, offset=offset)

    def get(self, item_id: int) -> PrepItem:
        item = self.items.get(item_id)
        if item is None:
            raise NotFoundError("Prep item", item_id)
        return item

    def create(self, data: PrepItemCreate) -> PrepItem:
        item = self.items.add(PrepItem(**data.model_dump()))
        self.session.commit()
        self.session.refresh(item)
        return item

    def update(self, item_id: int, data: PrepItemUpdate) -> PrepItem:
        item = self.get(item_id)
        apply_patch(item, data)
        self.session.commit()
        self.session.refresh(item)
        return item

    def delete(self, item_id: int) -> None:
        self.items.delete(self.get(item_id))
        self.session.commit()
