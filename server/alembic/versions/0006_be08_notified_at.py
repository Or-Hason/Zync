"""Add notified_at column to jobs for notification deduplication.

Marks when a job-match notification was emitted so subsequent scraper ticks
never re-emit for the same job row.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("notified_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "notified_at")
