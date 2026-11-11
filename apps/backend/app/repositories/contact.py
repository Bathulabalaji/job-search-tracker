from sqlalchemy import or_, select

from app.models.contact import Contact
from app.models.enums import ContactRole
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    def list(
        self,
        *,
        opportunity_id: int | None,
        role: ContactRole | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> list[Contact]:
        stmt = select(Contact).where(Contact.user_id == self.user_id)
        if opportunity_id is not None:
            stmt = stmt.where(Contact.opportunity_id == opportunity_id)
        if role is not None:
            stmt = stmt.where(Contact.role == role)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(like), Contact.company.ilike(like), Contact.email.ilike(like)
                )
            )
        stmt = stmt.order_by(Contact.name, Contact.id).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))
