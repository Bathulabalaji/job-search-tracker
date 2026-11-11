from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.contact import Contact
from app.models.enums import ContactRole
from app.repositories.contact import ContactRepository
from app.repositories.opportunity import OpportunityRepository
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.common import apply_patch


class ContactService:
    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.contacts = ContactRepository(session, user_id)
        self.opportunities = OpportunityRepository(session, user_id)

    def list(
        self,
        *,
        opportunity_id: int | None = None,
        role: ContactRole | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        return self.contacts.list(
            opportunity_id=opportunity_id, role=role, q=q, limit=limit, offset=offset
        )

    def get(self, contact_id: int) -> Contact:
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise NotFoundError("Contact", contact_id)
        return contact

    def create(self, data: ContactCreate) -> Contact:
        self._require_opportunity(data.opportunity_id)
        contact = self.contacts.add(Contact(**data.model_dump()))
        self.session.commit()
        self.session.refresh(contact)
        return contact

    def update(self, contact_id: int, data: ContactUpdate) -> Contact:
        contact = self.get(contact_id)
        if "opportunity_id" in data.model_fields_set:
            self._require_opportunity(data.opportunity_id)
        apply_patch(contact, data)
        self.session.commit()
        self.session.refresh(contact)
        return contact

    def delete(self, contact_id: int) -> None:
        self.contacts.delete(self.get(contact_id))
        self.session.commit()

    def _require_opportunity(self, opportunity_id: int | None) -> None:
        if opportunity_id is not None and self.opportunities.get(opportunity_id) is None:
            raise NotFoundError("Opportunity", opportunity_id)
