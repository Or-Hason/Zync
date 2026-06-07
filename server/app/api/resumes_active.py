"""Active-resume endpoints, split out to keep each API module focused.

Single-active is enforced in application logic (not a DB constraint): activating
one resume clears the flag on every other. ``load_active_resume`` is the shared
query used by both this module and the job scoring pipeline.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import ActiveResumeResponse, ResumeRead

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger(__name__)


async def load_active_resume(db: AsyncSession) -> Resume | None:
    """Return the active resume row, or ``None`` when none is active.

    Args:
        db: Injected async DB session.

    Returns:
        The active :class:`Resume`, or ``None``.
    """
    stmt = select(Resume).where(Resume.is_active.is_(True)).limit(1)
    rows = (await db.execute(stmt)).scalars().all()
    return rows[0] if rows else None


@router.get(
    "/active",
    response_model=ActiveResumeResponse,
    summary="Get the currently active resume",
)
async def get_active_resume(
    db: AsyncSession = Depends(get_db),
) -> ActiveResumeResponse:
    """Return the active resume (id, version_name, structured_data).

    Args:
        db: Injected async DB session.

    Returns:
        The active resume record.

    Raises:
        HTTPException: 404 if no resume is currently active.
    """
    resume = await load_active_resume(db)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active resume."
        )
    return ActiveResumeResponse.model_validate(resume)


@router.put(
    "/{resume_id}/set-active",
    response_model=ResumeRead,
    summary="Mark a resume active (clears the flag on all others)",
)
async def set_active_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    """Set the target resume active and deactivate every other resume.

    Args:
        resume_id: Target resume primary key.
        db: Injected async DB session.

    Returns:
        The updated (now active) resume record.

    Raises:
        HTTPException: 404 if no resume matches ``resume_id``.
    """
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )

    stmt = select(Resume).where(Resume.is_active.is_(True))
    for other in (await db.execute(stmt)).scalars().all():
        if other.id != resume_id:
            other.is_active = False
    resume.is_active = True

    await db.flush()
    await db.refresh(resume)

    logger.info("Active resume changed", extra={"resume_id": str(resume.id)})
    return ResumeRead.model_validate(resume)
