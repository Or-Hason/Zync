from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.job import Job
from app.models.resume import Resume


class Application(Base):
    """Links a Job to the Resume used when applying, with application metadata."""

    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    application_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="applications")
    resume: Mapped[Resume] = relationship("Resume", back_populates="applications")
