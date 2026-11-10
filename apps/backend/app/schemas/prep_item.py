from typing import Annotated

from pydantic import BaseModel, Field

from app.models.enums import PrepCategory, PrepStatus
from app.schemas.common import ORMModel, PatchModel

Confidence = Annotated[int, Field(ge=1, le=5)]


class PrepItemCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    category: PrepCategory
    status: PrepStatus = PrepStatus.todo
    confidence: Confidence = 1
    notes: str | None = Field(default=None, max_length=4000)


class PrepItemUpdate(PatchModel):
    non_nullable = frozenset({"topic", "category", "status", "confidence"})

    topic: str | None = Field(default=None, min_length=1, max_length=300)
    category: PrepCategory | None = None
    status: PrepStatus | None = None
    confidence: Confidence | None = None
    notes: str | None = Field(default=None, max_length=4000)


class PrepItemRead(ORMModel):
    id: int
    topic: str
    category: PrepCategory
    status: PrepStatus
    confidence: int
    notes: str | None
