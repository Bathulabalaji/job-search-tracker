"""resume-to-job matches, search profiles and recommendations

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("job_posting_id", sa.Integer(), nullable=True),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("jd_hash", sa.String(length=40), nullable=False),
        sa.Column("resume_hash", sa.String(length=64), nullable=False),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column("llm_score", sa.Integer(), nullable=True),
        sa.Column("matched_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(opportunity_id IS NOT NULL) <> (job_posting_id IS NOT NULL)",
            name=op.f("ck_job_matches_exactly_one_target"),
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_opportunity", "job_matches", ["user_id", "opportunity_id"])
    op.create_index("ix_job_matches_posting", "job_matches", ["user_id", "job_posting_id"])

    op.create_table(
        "job_search_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "title_keywords",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "work_modes",
            postgresql.ARRAY(sa.String(length=16)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("min_vector_score", sa.Float(), server_default="0.55", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "derived_from_resume_ids",
            postgresql.ARRAY(sa.Integer()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_search_profiles_user_id", "job_search_profiles", ["user_id"])
    op.create_index("uq_job_search_profiles_user", "job_search_profiles", ["user_id"], unique=True)

    op.create_table(
        "job_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), nullable=False),
        sa.Column("best_resume_id", sa.Integer(), nullable=True),
        sa.Column("vector_score", sa.Float(), nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["best_resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_recommendations_user_id", "job_recommendations", ["user_id"])
    op.create_index(
        "uq_job_recommendations_user_posting",
        "job_recommendations",
        ["user_id", "job_posting_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("job_recommendations")
    op.drop_table("job_search_profiles")
    op.drop_table("job_matches")
