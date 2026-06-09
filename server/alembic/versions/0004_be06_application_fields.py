"""Job application options and recommended apply method

Adds:
- ``jobs.application_options`` JSONB — discovered email addresses and ATS URLs
  extracted from the job post during Ollama parsing.
- ``jobs.recommended_apply_method`` Text — the single most direct application
  channel; defaults to the platform's native button when none is detected.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("application_options", JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("recommended_apply_method", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "recommended_apply_method")
    op.drop_column("jobs", "application_options")
