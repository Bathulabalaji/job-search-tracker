from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import ContactServiceDep
from app.models.contact import Contact
from app.models.enums import ContactRole
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactRead])
def list_contacts(
    service: ContactServiceDep,
    opportunity_id: int | None = None,
    role: ContactRole | None = None,
    q: Annotated[str | None, Query(description="Search name, company or email")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Contact]:
    return service.list(opportunity_id=opportunity_id, role=role, q=q, limit=limit, offset=offset)


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(data: ContactCreate, service: ContactServiceDep) -> Contact:
    return service.create(data)


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(contact_id: int, service: ContactServiceDep) -> Contact:
    return service.get(contact_id)


@router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(contact_id: int, data: ContactUpdate, service: ContactServiceDep) -> Contact:
    return service.update(contact_id, data)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, service: ContactServiceDep) -> Response:
    service.delete(contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
