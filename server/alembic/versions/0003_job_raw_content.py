"""Job raw content for AI-independent duplicate detection

Adds:
- ``jobs.raw_content`` Text — the normalised raw ingested text (URL extract or
  pasted body). Duplicate detection compares this instead of the AI-parsed
  title/description, so near-identical postings are still caught when the local
  model rephrases the parsed output between runs.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("raw_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "raw_content")
