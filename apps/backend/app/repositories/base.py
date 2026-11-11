from typing import cast

from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.mixins import OwnedMixin


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.user_id = user_id

    def get(self, entity_id: int) -> ModelT | None:
        """Another user's row is indistinguishable from a missing one."""
        obj = self.session.get(self.model, entity_id)
        if obj is None or cast(OwnedMixin, obj).user_id != self.user_id:
            return None
        return obj

    def add(self, obj: ModelT) -> ModelT:
        # Ownership is always taken from the authenticated user, never from the request body.
        cast(OwnedMixin, obj).user_id = self.user_id
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.flush()
