from pydantic import BaseModel, Field

from app.models.enums import ContactRole
from app.schemas.common import ORMModel, PatchModel


class ContactCreate(BaseModel):
    opportunity_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    role: ContactRole = ContactRole.recruiter
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=50)
    linkedin_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = None


class ContactUpdate(PatchModel):
    non_nullable = frozenset({"name", "role"})

    opportunity_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: ContactRole | None = None
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=50)
    linkedin_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = None


class ContactRead(ORMModel):
    id: int
    opportunity_id: int | None
    name: str
    role: ContactRole
    company: str | None
    email: str | None
    phone: str | None
    linkedin_url: str | None
    notes: str | None
