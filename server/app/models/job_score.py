from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.resume import Resume


class JobScore(Base):
    """One AI match score for a (job, resume) pair.

    Bridging table between ``jobs`` and ``resumes``: scoring the same job with a
    different CV adds a row here instead of duplicating the job row. The unique
    constraint guarantees a given CV holds at most one score per job, so a
    re-score is an UPSERT rather than an append.
    """

    __tablename__ = "job_scores"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uq_job_scores_job_resume"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE", name="fk_job_scores_job"),
        nullable=False,
    )
    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE", name="fk_job_scores_resume"),
        nullable=False,
    )
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # Non-score Gemini output kept as flexible JSONB so the cache can replay it:
    # { "rationale": str, "matched_skills": [...], "missing_skills": [...] }.
    score_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    # Bumped on every re-score so the UI can tell a stale score from a fresh one.
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ``selectin`` (not lazy) because the async engine raises MissingGreenlet on
    # implicit lazy loads; the resume is always needed to label the score in the UI.
    job: Mapped[Job] = relationship("Job", back_populates="scores")
    resume: Mapped[Resume] = relationship(
        "Resume", back_populates="scores", lazy="selectin"
    )
