from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PrepCategory, PrepStatus
from app.models.types import enum_column


class PrepItem(Base):
    __tablename__ = "prep_items"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 1 AND 5", name="confidence_range"),
        Index("ix_prep_items_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(300))
    category: Mapped[PrepCategory] = mapped_column(enum_column(PrepCategory))
    status: Mapped[PrepStatus] = mapped_column(enum_column(PrepStatus), default=PrepStatus.todo)
    confidence: Mapped[int] = mapped_column(default=1, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
