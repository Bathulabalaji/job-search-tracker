from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import OwnedMixin


class Resume(OwnedMixin, Base):
    """A resume version: metadata, plus (since Phase 2) an optional uploaded PDF.

    The file itself lives in object storage under `storage_key`; only redacted text, the
    extracted profile and chunk embeddings are kept in the database.
    """

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    focus: Mapped[str | None] = mapped_column(String(200))
    file_name: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50), default="1", server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)

    # ---- the document (all NULL/none until a file is uploaded) -----------------------------
    storage_key: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None]
    sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None]
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text_status: Mapped[str] = mapped_column(String(16), default="none", server_default="none")
    embed_status: Mapped[str] = mapped_column(String(16), default="none", server_default="none")
    embed_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    embed_retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(String(500))
    extracted_text: Mapped[str | None] = mapped_column(Text)  # redacted
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    profile_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def document(self) -> dict[str, Any] | None:
        """What the API shows about the file (see ResumeDocumentRead); None without one."""
        if self.storage_key is None:
            return None
        return {
            "file_name": self.file_name,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "page_count": self.page_count,
            "uploaded_at": self.uploaded_at,
            "text_status": self.text_status,
            "embed_status": self.embed_status,
            "processing_error": self.processing_error,
            "profile": self.profile,
        }


class ResumeChunk(OwnedMixin, Base):
    """A passage of a resume with its embedding.

    The `embedding` column is deliberately not mapped here: it is `vector(768)` where the
    pgvector extension exists (Neon, CI) and `double precision[]` where it does not (a plain
    local Postgres). `ResumeChunkRepository` reads and writes it with SQL that fits either.
    """

    __tablename__ = "resume_chunks"
    __table_args__ = (
        Index("uq_resume_chunks_resume_index", "resume_id", "chunk_index", unique=True),
        Index("ix_resume_chunks_user_resume", "user_id", "resume_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]
    section: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@dataclass(frozen=True)
class SimilarChunk:
    """A search hit from `ResumeChunkRepository.similar`."""

    chunk_id: int
    resume_id: int
    chunk_index: int
    section: str
    text: str
    score: float  # cosine similarity, 1.0 = identical
