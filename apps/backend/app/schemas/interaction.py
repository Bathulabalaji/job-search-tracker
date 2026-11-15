from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.enums import Direction, InteractionType, Stage
from app.schemas.common import ORMModel, PatchModel

SUMMARY_MAX_CHARS = 2000


def _clean_summary(value: str) -> str:
    """A logged activity must say what happened: trimmed, not blank, not huge."""
    text = value.replace("\x00", "").strip()
    if not text:
        raise ValueError("Add a short summary of what happened")
    if len(text) > SUMMARY_MAX_CHARS:
        raise ValueError(f"Keep the summary under {SUMMARY_MAX_CHARS} characters")
    return text


class InteractionCreate(BaseModel):
    opportunity_id: int
    contact_id: int | None = None
    type: InteractionType
    direction: Direction = Direction.out
    summary: str
    occurred_at: datetime | None = None  # defaults to now; never in the future

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        return _clean_summary(value)

    @field_validator("type")
    @classmethod
    def _not_stage_change(cls, value: InteractionType) -> InteractionType:
        # Stage changes are written by the server when a stage moves, never by a client.
        if value is InteractionType.stage_change:
            raise ValueError("Stage changes are recorded automatically when you move a stage")
        return value


class InteractionUpdate(PatchModel):
    non_nullable = frozenset({"type", "direction", "occurred_at", "summary"})

    contact_id: int | None = None
    type: InteractionType | None = None
    direction: Direction | None = None
    summary: str | None = None
    occurred_at: datetime | None = None

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str | None) -> str | None:
        return None if value is None else _clean_summary(value)


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
