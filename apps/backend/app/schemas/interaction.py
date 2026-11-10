from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Direction, InteractionType, Stage
from app.schemas.common import ORMModel, PatchModel


class InteractionCreate(BaseModel):
    opportunity_id: int
    contact_id: int | None = None
    type: InteractionType
    direction: Direction = Direction.out
    summary: str | None = None
    occurred_at: datetime | None = None  # defaults to now


class InteractionUpdate(PatchModel):
    non_nullable = frozenset({"type", "direction", "occurred_at"})

    contact_id: int | None = None
    type: InteractionType | None = None
    direction: Direction | None = None
    summary: str | None = None
    occurred_at: datetime | None = None


class InteractionRead(ORMModel):
    id: int
    opportunity_id: int
    contact_id: int | None
    type: InteractionType
    direction: Direction
    summary: str | None
    occurred_at: datetime
    from_stage: Stage | None = None
    to_stage: Stage | None = None
