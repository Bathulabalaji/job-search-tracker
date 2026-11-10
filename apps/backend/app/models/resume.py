from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Resume(Base):
    """Metadata about a resume version. The file itself is never stored."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    focus: Mapped[str | None] = mapped_column(String(200))
    file_name: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50), default="1", server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
