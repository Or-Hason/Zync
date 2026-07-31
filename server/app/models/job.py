from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job_score import JobScore

logger = logging.getLogger(__name__)

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

_STATUS_CHECK = "status IN ({})".format(", ".join(f"'{s}'" for s in _VALID_STATUSES))


class Job(Base):
    """Represents a scraped or manually entered job listing."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="ck_jobs_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Normalised raw ingested text, used for AI-independent duplicate detection.
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_applied",
        server_default="not_applied",
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    duplicate_chance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recommended_apply_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    # Set when a job-match notification is emitted; prevents re-emission on
    # subsequent scraper ticks for the same job row.
    notified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Set when the user opens the job detail page. Drives the Unread filter.
    # Intentionally separate from notified_at — a notification being sent does
    # not mean the user has read the job.
    viewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    applications: Mapped[list[Application]] = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )
    # Every (CV, score) pair recorded for this job. Eager-loaded because the
    # async engine raises MissingGreenlet on an implicit lazy load, and every
    # consumer of a Job needs its scores.
    scores: Mapped[list[JobScore]] = relationship(
        "JobScore",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
