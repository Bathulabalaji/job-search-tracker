from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FollowupChannel, FollowupStatus
from app.models.types import enum_column


class Followup(Base):
    __tablename__ = "followups"
    __table_args__ = (Index("ix_followups_status_due", "status", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    due_date: Mapped[date] = mapped_column(Date)
    channel: Mapped[FollowupChannel] = mapped_column(
        enum_column(FollowupChannel), default=FollowupChannel.email
    )
    message_draft: Mapped[str | None] = mapped_column(Text)
    status: Mapped[FollowupStatus] = mapped_column(
        enum_column(FollowupStatus), default=FollowupStatus.pending
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
