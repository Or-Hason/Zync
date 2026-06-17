from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class CoverLetter(Base):
    """A Gemini-generated cover letter tied to a unique (job_id, resume_id) pair.

    The unique constraint is enforced at the DB level so the API can safely
    return HTTP 409 on duplicate generation attempts.
    """

    __tablename__ = "cover_letters"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uq_cover_letters_job_resume"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE", name="fk_cover_letters_job"),
        nullable=False,
    )
    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE", name="fk_cover_letters_resume"),
        nullable=False,
    )
    original_template_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    gemini_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
