from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import FollowupChannel, FollowupStatus
from app.schemas.common import ORMModel, PatchModel


class FollowupCreate(BaseModel):
    opportunity_id: int
    due_date: date
    channel: FollowupChannel = FollowupChannel.email
    message_draft: str | None = None


class FollowupUpdate(PatchModel):
    """Snooze = change due_date. Done/skip = change status (done_at is managed for you)."""

    non_nullable = frozenset({"due_date", "channel", "status"})

    due_date: date | None = None
    channel: FollowupChannel | None = None
    message_draft: str | None = None
    status: FollowupStatus | None = None


class FollowupRead(ORMModel):
    id: int
    opportunity_id: int
    due_date: date
    channel: FollowupChannel
    message_draft: str | None
    status: FollowupStatus
    done_at: datetime | None
