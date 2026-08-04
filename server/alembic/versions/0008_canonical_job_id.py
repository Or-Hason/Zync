"""Add canonical_job_id to jobs for rescore variant tracking.

When a job is rescored with a different resume, a new child row is created.
canonical_job_id points to the original canonical row (NULL for canonical rows).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("canonical_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_canonical_job",
        "jobs",
        "jobs",
        ["canonical_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_canonical_job", "jobs", type_="foreignkey")
    op.drop_column("jobs", "canonical_job_id")
