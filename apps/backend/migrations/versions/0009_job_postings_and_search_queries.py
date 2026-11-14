"""job postings cache, search queries, tracked postings and chat attachments

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("fingerprint", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("work_mode", sa.String(length=16), nullable=True),
        sa.Column("source_site", sa.String(length=16), server_default="other", nullable=False),
        sa.Column("apply_url", sa.String(length=1000), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salary_text", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("active_status", sa.String(length=16), server_default="unknown", nullable=False),
        sa.Column("active_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_postings")),
    )
    op.create_index("uq_job_postings_canonical_url", "job_postings", ["canonical_url"], unique=True)
    op.create_index("ix_job_postings_fingerprint", "job_postings", ["fingerprint"])
    op.create_index("ix_job_postings_expires_at", "job_postings", ["expires_at"])

    op.create_table(
        "job_search_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("cache_key", sa.String(length=40), nullable=False),
        sa.Column("query_text", sa.String(length=300), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "providers_used",
            postgresql.ARRAY(sa.String(length=32)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "result_ids", postgresql.ARRAY(sa.Integer()), server_default="{}", nullable=False
        ),
        sa.Column("notices", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_job_search_queries_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_search_queries")),
    )
    op.create_index(op.f("ix_job_search_queries_user_id"), "job_search_queries", ["user_id"])
    op.create_index(
        "ix_job_search_queries_user_key", "job_search_queries", ["user_id", "cache_key"]
    )

    op.add_column("opportunities", sa.Column("job_posting_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_opportunities_job_posting_id_job_postings"),
        "opportunities",
        "job_postings",
        ["job_posting_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_opportunities_user_job_posting",
        "opportunities",
        ["user_id", "job_posting_id"],
        unique=True,
        postgresql_where=sa.text("job_posting_id IS NOT NULL"),
    )

    op.add_column(
        "chat_messages",
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "attachments")
    op.drop_index("uq_opportunities_user_job_posting", table_name="opportunities")
    op.drop_constraint(
        op.f("fk_opportunities_job_posting_id_job_postings"), "opportunities", type_="foreignkey"
    )
    op.drop_column("opportunities", "job_posting_id")
    op.drop_index("ix_job_search_queries_user_key", table_name="job_search_queries")
    op.drop_index(op.f("ix_job_search_queries_user_id"), table_name="job_search_queries")
    op.drop_table("job_search_queries")
    op.drop_index("ix_job_postings_expires_at", table_name="job_postings")
    op.drop_index("ix_job_postings_fingerprint", table_name="job_postings")
    op.drop_index("uq_job_postings_canonical_url", table_name="job_postings")
    op.drop_table("job_postings")
