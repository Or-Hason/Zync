"""Initial tables: jobs, resumes, applications

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALID_STATUSES = (
    "not_applied",
    "applied",
    "auto_rejected",
    "user_rejected",
    "assessment_task",
    "assessment_rejected",
    "home_test",
    "home_test_rejected",
    "professional_interview",
    "professional_interview_rejected",
    "hr_interview",
    "hr_interview_rejected",
    "accepted",
)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("company_description", sa.Text, nullable=True),
        sa.Column("job_description", sa.Text, nullable=True),
        sa.Column("requirements", JSONB, nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("search_filters", JSONB, nullable=True),
        sa.Column("match_score", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="not_applied",
        ),
        sa.Column(
            "is_duplicate",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("duplicate_chance", sa.Integer, nullable=True),
        sa.Column("published_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ({})".format(
                ", ".join(f"'{s}'" for s in _VALID_STATUSES)
            ),
            name="ck_jobs_status",
        ),
    )

    op.create_table(
        "resumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("version_name", sa.String(255), nullable=False),
        sa.Column("target_role", sa.String(255), nullable=True),
        sa.Column("structured_data", JSONB, nullable=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "applied_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("application_method", sa.String(255), nullable=True),
        sa.Column("cover_letter_text", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_applications_job_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
            name="fk_applications_resume_id",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("resumes")
    op.drop_table("jobs")
