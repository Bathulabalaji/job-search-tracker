"""resume documents (uploaded PDFs) and chunk embeddings

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14 12:00:00.000000

The embedding column is `vector(768)` with an HNSW index where the pgvector extension can
be installed (Neon, CI images), and a plain `double precision[]` elsewhere, so a developer's
stock Postgres still runs every migration and test. The application detects which it got.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMS = 768


def _pgvector_available() -> bool:
    row = op.get_bind().execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar()
    return row is not None


def upgrade() -> None:
    with_vector = _pgvector_available()
    if with_vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("resumes", sa.Column("storage_key", sa.String(length=500), nullable=True))
    op.add_column("resumes", sa.Column("content_type", sa.String(length=100), nullable=True))
    op.add_column("resumes", sa.Column("size_bytes", sa.Integer(), nullable=True))
    op.add_column("resumes", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("resumes", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("resumes", sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "resumes",
        sa.Column("text_status", sa.String(length=16), server_default="none", nullable=False),
    )
    op.add_column(
        "resumes",
        sa.Column("embed_status", sa.String(length=16), server_default="none", nullable=False),
    )
    op.add_column(
        "resumes", sa.Column("embed_attempts", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "resumes", sa.Column("embed_retry_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("resumes", sa.Column("processing_error", sa.String(length=500), nullable=True))
    op.add_column("resumes", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column(
        "resumes", sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("resumes", sa.Column("profile_model", sa.String(length=100), nullable=True))
    op.add_column(
        "resumes",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.add_column(
        "resumes",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )

    op.create_table(
        "resume_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"], name=op.f("fk_resume_chunks_resume_id_resumes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_resume_chunks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_chunks")),
    )
    op.create_index(op.f("ix_resume_chunks_user_id"), "resume_chunks", ["user_id"])
    op.create_index(
        "uq_resume_chunks_resume_index", "resume_chunks", ["resume_id", "chunk_index"], unique=True
    )
    op.create_index("ix_resume_chunks_user_resume", "resume_chunks", ["user_id", "resume_id"])
    if with_vector:
        op.execute(f"ALTER TABLE resume_chunks ADD COLUMN embedding vector({EMBEDDING_DIMS})")
        op.execute(
            "CREATE INDEX ix_resume_chunks_embedding ON resume_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
    else:
        op.execute("ALTER TABLE resume_chunks ADD COLUMN embedding double precision[]")


def downgrade() -> None:
    op.drop_table("resume_chunks")
    for column in (
        "updated_at", "created_at", "profile_model", "profile", "extracted_text",
        "processing_error", "embed_retry_after", "embed_attempts", "embed_status", "text_status",
        "uploaded_at", "page_count", "sha256", "size_bytes", "content_type", "storage_key",
    ):
        op.drop_column("resumes", column)
