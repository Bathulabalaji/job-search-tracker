import uuid
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel, PatchModel


class ConversationRead(ORMModel):
    id: int
    title: str
    status: str
    last_message_at: datetime
    created_at: datetime


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(None, max_length=120)


class ConversationUpdate(PatchModel):
    model_config = ConfigDict(extra="forbid")
    non_nullable: ClassVar[frozenset[str]] = frozenset({"title", "status"})

    title: str | None = Field(None, min_length=1, max_length=120)
    status: Literal["active", "archived"] | None = None


class MessageRead(ORMModel):
    id: int
    seq: int
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    status: str
    error_code: str | None
    model: str | None
    run_id: uuid.UUID | None
    created_at: datetime


class RunRead(ORMModel):
    id: uuid.UUID
    status: str
    error_code: str | None
    model_switches: int
    started_at: datetime
    finished_at: datetime | None
    resumable: bool = False


class ConversationDetail(BaseModel):
    conversation: ConversationRead
    messages: list[MessageRead]
    # The latest run, so a client can offer "Retry" after a capacity failure on reload.
    last_run: RunRead | None


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=2000)
    client_message_id: uuid.UUID

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Type a message first")
        return value.strip()


class QuotaRead(BaseModel):
    limit: int
    used: int


class ChatConfig(BaseModel):
    enabled: bool
    messages_per_day: QuotaRead
    max_message_chars: int = 2000
    suggestions: list[str]
