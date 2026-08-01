"""Read/unread mutations and the skills catalogue for the Explorer view.

Split out of ``job_repository.py`` — see ``app/services/job_repository.py`` for the re-exported public API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


async def mark_all_jobs_read(db: AsyncSession) -> int:
    """Set viewed_at to now() on every unread job row.

    Args:
        db: Active async DB session.

    Returns:
        The number of rows updated.
    """
    from sqlalchemy import update

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Job)
        .where(Job.viewed_at.is_(None))
        .values(viewed_at=now)
    )
    await db.flush()
    return result.rowcount


async def mark_job_read(db: AsyncSession, job_id: UUID) -> None:
    """Set viewed_at to now() on a job if it has not been viewed yet.

    This is the authoritative write for the Explorer's Unread filter.
    Intentionally leaves notified_at untouched — that column belongs
    exclusively to the notification deduplication system.
    Idempotent — no-op if the job was already marked as read.

    Args:
        db: Active async DB session.
        job_id: The job to mark as read.
    """
    job = await db.get(Job, job_id)
    if job is not None and job.viewed_at is None:
        job.viewed_at = datetime.now(timezone.utc)
        await db.flush()


async def list_job_skills(db: AsyncSession) -> list[str]:
    """Return all distinct skill strings across all jobs' JSONB requirements.

    Unions the ``skills`` and ``recommended_skills`` arrays from every row so
    the Explorer's skill autocomplete reflects the full catalogue.

    Args:
        db: Active async DB session.

    Returns:
        Alphabetically sorted, deduplicated skill strings.
    """
    stmt = text("""
        SELECT DISTINCT skill
        FROM (
            SELECT jsonb_array_elements_text(requirements->'skills') AS skill
            FROM jobs
            WHERE requirements IS NOT NULL
            UNION
            SELECT jsonb_array_elements_text(requirements->'recommended_skills') AS skill
            FROM jobs
            WHERE requirements IS NOT NULL
        ) t
        WHERE skill IS NOT NULL AND skill <> ''
        ORDER BY skill
    """)
    rows = (await db.execute(stmt)).all()
    return [row[0] for row in rows]
