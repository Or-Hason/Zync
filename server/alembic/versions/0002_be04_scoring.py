"""BE-04 scoring: settings table, active resume, score columns

Adds:
- ``settings`` singleton table (JSONB blob, CHECK id = 1).
- ``resumes.is_active`` boolean (single-active enforced in app logic).
- ``jobs.scored_by_resume_id`` UUID FK -> resumes.id (ON DELETE SET NULL).
- ``jobs.score_details`` JSONB (rationale + matched/missing skills for caching).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app.models.settings.SETTINGS_ROW_ID — the singleton row's fixed PK.
_SETTINGS_ROW_ID = 1


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("data", JSONB, nullable=False),
        sa.CheckConstraint(f"id = {_SETTINGS_ROW_ID}", name="ck_settings_singleton"),
    )

    op.add_column(
        "resumes",
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "jobs",
        sa.Column("scored_by_resume_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column("jobs", sa.Column("score_details", JSONB, nullable=True))
    op.create_foreign_key(
        "fk_jobs_scored_by_resume",
        source_table="jobs",
        referent_table="resumes",
        local_cols=["scored_by_resume_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_scored_by_resume", "jobs", type_="foreignkey")
    op.drop_column("jobs", "score_details")
    op.drop_column("jobs", "scored_by_resume_id")
    op.drop_column("resumes", "is_active")
    op.drop_table("settings")
