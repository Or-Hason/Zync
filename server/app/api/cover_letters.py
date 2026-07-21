"""Cover letter API: generate and retrieve per-job cover letters."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.cover_letter import CoverLetter
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.cover_letter import CoverLetterRead, CoverLetterUpdate
from app.services.cover_letter_service import generate_cover_letter
from app.services.gemini_client import GeminiUnavailableError, get_gemini_client
from app.services.settings_store import SettingsStore, get_settings_store

router = APIRouter(prefix="/jobs/{job_id}/cover-letter", tags=["cover-letters"])
logger = logging.getLogger(__name__)


async def _load_job(job_id: UUID, db: AsyncSession) -> Job:
    """Return the Job row or raise HTTP 404.

    Args:
        job_id: UUID of the job to load.
        db: Active async DB session.

    Returns:
        The :class:`Job` ORM instance.

    Raises:
        HTTPException: 404 when the job does not exist.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


async def _load_resume(resume_id: UUID, db: AsyncSession) -> Resume:
    """Return the Resume row or raise HTTP 404.

    Args:
        resume_id: UUID of the resume to load.
        db: Active async DB session.

    Returns:
        The :class:`Resume` ORM instance.

    Raises:
        HTTPException: 404 when the resume does not exist.
    """
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return resume


@router.get(
    "",
    response_model=CoverLetterRead,
    summary="Get the cover letter for a job+resume pair",
)
async def get_cover_letter(
    job_id: UUID,
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CoverLetterRead:
    """Return the existing cover letter for ``(job_id, resume_id)``.

    Raises:
        HTTPException: 404 when no letter has been generated yet.
    """
    result = await db.execute(
        select(CoverLetter).where(
            CoverLetter.job_id == job_id,
            CoverLetter.resume_id == resume_id,
        )
    )
    letter = result.scalar_one_or_none()
    if letter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover letter found for this job and resume combination.",
        )
    return CoverLetterRead.model_validate(letter)


@router.post(
    "",
    response_model=CoverLetterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a cover letter for a job+resume pair",
)
async def create_cover_letter(
    job_id: UUID,
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    store: SettingsStore = Depends(get_settings_store),
) -> CoverLetterRead:
    """Generate a cover letter using Gemini and persist the result.

    Requires the letter template to be present in settings. Returns HTTP 409
    if a letter already exists for this ``(job_id, resume_id)`` pair.

    Raises:
        HTTPException: 404 job/resume not found; 400 no template; 409 already exists;
            503 Gemini unavailable.
    """
    job = await _load_job(job_id, db)
    resume = await _load_resume(resume_id, db)

    template = await store.get_letter_template()
    template_text: str | None = template.get("text")
    if not template_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No letter template found. Upload one in Documents Manager first.",
        )

    gemini = get_gemini_client()

    try:
        generated_text, summary = await generate_cover_letter(
            template_text=template_text,
            job=job,
            resume=resume,
            gemini=gemini,
        )
    except GeminiUnavailableError as exc:
        logger.error("Gemini unavailable during cover letter generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again later.",
        ) from exc
    except ValueError as exc:
        logger.error("Cover letter generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate cover letter. Please try again.",
        ) from exc

    letter = CoverLetter(
        job_id=job_id,
        resume_id=resume_id,
        original_template_text=template_text,
        generated_text=generated_text,
        gemini_summary=summary or None,
    )
    db.add(letter)

    try:
        await db.commit()
        await db.refresh(letter)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cover letter already exists for this job and resume combination.",
        )

    logger.info(
        "Cover letter generated",
        extra={"job_id": str(job_id), "resume_id": str(resume_id)},
    )
    return CoverLetterRead.model_validate(letter)


@router.patch(
    "",
    response_model=CoverLetterRead,
    summary="Update the generated text of an existing cover letter",
)
async def update_cover_letter(
    job_id: UUID,
    resume_id: UUID,
    payload: CoverLetterUpdate,
    db: AsyncSession = Depends(get_db),
) -> CoverLetterRead:
    """Persist user edits to the generated cover letter text.

    Raises:
        HTTPException: 404 when no letter exists for this job+resume pair.
    """
    result = await db.execute(
        select(CoverLetter).where(
            CoverLetter.job_id == job_id,
            CoverLetter.resume_id == resume_id,
        )
    )
    letter = result.scalar_one_or_none()
    if letter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover letter found for this job and resume combination.",
        )
    letter.generated_text = payload.generated_text
    await db.commit()
    await db.refresh(letter)
    logger.info("Cover letter updated", extra={"job_id": str(job_id), "resume_id": str(resume_id)})
    return CoverLetterRead.model_validate(letter)
