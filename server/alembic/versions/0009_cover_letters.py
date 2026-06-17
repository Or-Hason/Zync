"""Add cover_letters table.

Each row represents a Gemini-generated cover letter tied to a unique
(job_id, resume_id) pair. The unique constraint prevents duplicate generation
and allows safe 409 conflict detection at the API layer.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_template_text", sa.Text(), nullable=True),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("gemini_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name="fk_cover_letters_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"],
            name="fk_cover_letters_resume",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cover_letters"),
        sa.UniqueConstraint("job_id", "resume_id", name="uq_cover_letters_job_resume"),
    )


def downgrade() -> None:
    op.drop_table("cover_letters")
