"""Add viewed_at column to jobs for user-read tracking.

Tracks when the user opened the job detail page, completely separate from
notified_at (which records when the background scanner emitted a push alert).
This column is the authoritative source for the Explorer's Unread filter.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("viewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "viewed_at")
