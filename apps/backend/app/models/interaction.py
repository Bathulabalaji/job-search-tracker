from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Direction, InteractionType, Stage
from app.models.mixins import OwnedMixin
from app.models.types import enum_column


class Interaction(OwnedMixin, Base):
    __tablename__ = "interactions"
    __table_args__ = (
        Index("ix_interactions_opportunity_occurred", "opportunity_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[InteractionType] = mapped_column(enum_column(InteractionType))
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), default=Direction.out)
    # Set only on stage_change records: structured history that funnel analytics reads.
    from_stage: Mapped[Stage | None] = mapped_column(enum_column(Stage, name="from_stage"))
    to_stage: Mapped[Stage | None] = mapped_column(enum_column(Stage, name="to_stage"))
    summary: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
