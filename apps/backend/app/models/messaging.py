"""Outreach: the sender's details, the user's own templates, and what was actually sent."""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class OutreachProfile(OwnedMixin, Base):
    """Who the messages come from. One per user. Everything is optional: a missing value
    becomes a visible gap in the draft instead of a wrong word."""

    __tablename__ = "outreach_profiles"
    __table_args__ = (Index("uq_outreach_profiles_user", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The address messages are sent from: signs them, and picks the Google account for the
    # Gmail compose link. (A mailto: link cannot choose the sending account.)
    from_email: Mapped[str | None] = mapped_column(String(254))
    headline: Mapped[str | None] = mapped_column(String(300))  # finishes "I'm ..."
    phone: Mapped[str | None] = mapped_column(String(50))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(200))
    notice_period: Mapped[str | None] = mapped_column(String(100))
    current_ctc: Mapped[str | None] = mapped_column(String(100))
    expected_ctc: Mapped[str | None] = mapped_column(String(100))
    career_story: Mapped[str | None] = mapped_column(String(500))  # the career-switch bridge
    proof_points: Mapped[list[str]] = mapped_column(JSONB, default=list)
    india_style: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MessageTemplate(OwnedMixin, Base):
    """A template the user wrote or edited. A row with base_key replaces that built-in
    template's variant for this user; deleting the row restores the original."""

    __tablename__ = "message_templates"
    __table_args__ = (Index("ix_message_templates_user_base", "user_id", "base_key", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    base_key: Mapped[str | None] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(16))  # email | linkedin | linkedin_note
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    stages: Mapped[list[str]] = mapped_column(ARRAY(String(24)), default=list, server_default="{}")
    recipient_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), default=list, server_default="{}"
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OutreachMessage(OwnedMixin, Base):
    """A snapshot of a message the user marked as sent. The text is copied, not referenced,
    because the template may be edited afterwards."""

    __tablename__ = "outreach_messages"
    __table_args__ = (
        Index("ix_outreach_messages_opportunity_sent", "opportunity_id", "sent_at"),
        Index(
            "uq_outreach_messages_request",
            "user_id",
            "request_id",
            unique=True,
            postgresql_where=text("request_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    template_key: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(16))  # email | linkedin
    subject: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("interactions.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # makes a retried "sent" harmless
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = ["MessageTemplate", "OutreachMessage", "OutreachProfile"]
