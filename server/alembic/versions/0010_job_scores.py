"""Normalise scoring into a job_scores bridging table.

Replaces the "duplicate the whole job row per CV" model (``canonical_job_id`` +
per-row ``match_score``) with one row per (job, resume) pair.

Data handling (local-dev grade, per the refactor brief):
1. Backfill ``job_scores`` from every job row that carries a score.
2. Delete the duplicated rescore child rows (``canonical_job_id IS NOT NULL``);
   their scores survive in ``job_scores`` thanks to step 1.
3. Drop the now-redundant scoring columns from ``jobs``.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("score_details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_job_scores_job", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"], name="fk_job_scores_resume", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_scores"),
        sa.UniqueConstraint("job_id", "resume_id", name="uq_job_scores_job_resume"),
    )
    op.create_index("ix_job_scores_job_id", "job_scores", ["job_id"])
    op.create_index("ix_job_scores_resume_id", "job_scores", ["resume_id"])

    # Backfill: child rescore rows resolve back onto their canonical job, so a
    # canonical job ends up with one row per CV that ever scored it. DISTINCT ON
    # keeps the newest score when the same CV scored both parent and child.
    op.execute(
        """
        INSERT INTO job_scores (id, job_id, resume_id, match_score, score_details)
        SELECT DISTINCT ON (COALESCE(canonical_job_id, id), scored_by_resume_id)
               gen_random_uuid(),
               COALESCE(canonical_job_id, id),
               scored_by_resume_id,
               match_score,
               score_details
        FROM jobs
        WHERE match_score IS NOT NULL
          AND scored_by_resume_id IS NOT NULL
        ORDER BY COALESCE(canonical_job_id, id), scored_by_resume_id, created_at DESC
        ON CONFLICT ON CONSTRAINT uq_job_scores_job_resume DO NOTHING
        """
    )

    # The duplicated child rows exist only to carry historical scores, which are
    # now in job_scores — drop them so the Explorer sees one row per real job.
    op.execute("DELETE FROM jobs WHERE canonical_job_id IS NOT NULL")

    op.drop_constraint("fk_jobs_canonical_job", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_scored_by_resume", "jobs", type_="foreignkey")
    op.drop_column("jobs", "canonical_job_id")
    op.drop_column("jobs", "scored_by_resume_id")
    op.drop_column("jobs", "score_details")
    op.drop_column("jobs", "match_score")


def downgrade() -> None:
    op.add_column("jobs", sa.Column("match_score", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("score_details", postgresql.JSONB(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("scored_by_resume_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("canonical_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_scored_by_resume", "jobs", "resumes",
        ["scored_by_resume_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_jobs_canonical_job", "jobs", "jobs",
        ["canonical_job_id"], ["id"], ondelete="SET NULL",
    )

    # Best-effort restore: collapse each job's scores back onto the single set of
    # columns the old schema allowed, keeping the highest score. The per-CV rows
    # that exceeded that single slot cannot be represented and are lost.
    op.execute(
        """
        UPDATE jobs j
        SET match_score = s.match_score,
            score_details = s.score_details,
            scored_by_resume_id = s.resume_id
        FROM (
            SELECT DISTINCT ON (job_id) job_id, resume_id, match_score, score_details
            FROM job_scores
            ORDER BY job_id, match_score DESC
        ) s
        WHERE j.id = s.job_id
        """
    )

    op.drop_index("ix_job_scores_resume_id", table_name="job_scores")
    op.drop_index("ix_job_scores_job_id", table_name="job_scores")
    op.drop_table("job_scores")
