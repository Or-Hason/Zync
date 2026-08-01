"""Read projections consumed by the ingestion pipeline (dupes, score cache).

Split out of ``job_repository.py`` — see ``app/services/job_repository.py`` for the re-exported public API.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_score import JobScore
from app.services.duplicate_detection import ExistingJob
from app.services.score_cache import ScoredJob
from app.services.text_similarity import comparison_string

# Cap on existing rows pulled into memory for duplicate comparison.
DUPLICATE_SCAN_LIMIT = 500


async def load_existing_jobs(db: AsyncSession) -> list[ExistingJob]:
    """Load a capped, lightweight projection of jobs for duplicate detection.

    Args:
        db: Active async DB session.

    Returns:
        Up to :data:`DUPLICATE_SCAN_LIMIT` newest jobs as :class:`ExistingJob`.
    """
    stmt = (
        select(Job.raw_content, Job.created_at, Job.status)
        .order_by(Job.created_at.desc())
        .limit(DUPLICATE_SCAN_LIMIT)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ExistingJob(
            raw_content=row.raw_content,
            created_at=row.created_at,
            status=row.status,
        )
        for row in rows
    ]


async def load_scored_jobs(db: AsyncSession, resume_id: UUID) -> list[ScoredJob]:
    """Load jobs already scored with the given resume, for cache reuse.

    Args:
        db: Active async DB session.
        resume_id: The active resume's id.

    Returns:
        Scored jobs (``match_score`` present) as :class:`ScoredJob` projections.
    """
    stmt = (
        select(
            Job.id,
            Job.job_title,
            Job.job_description,
            JobScore.match_score,
            JobScore.score_details,
            Job.raw_content,
        )
        .join(JobScore, JobScore.job_id == Job.id)
        .where(JobScore.resume_id == resume_id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ScoredJob(
            comparison_text=comparison_string(row.job_title, row.job_description),
            match_score=row.match_score,
            score_details=row.score_details,
            job_id=row.id,
            raw_content=row.raw_content,
        )
        for row in rows
    ]


async def load_known_source_urls(db: AsyncSession) -> set[str]:
    """Return every non-null ``source_url`` currently stored in ``jobs``.

    Used by the scraper to skip URLs already discovered, so a job is never
    re-fetched or re-scored across scans.

    Args:
        db: Active async DB session.

    Returns:
        A set of known source URLs.
    """
    rows = (await db.execute(select(Job.source_url).where(Job.source_url.isnot(None)))).all()
    return {row.source_url for row in rows}


async def count_jobs_for_source(db: AsyncSession, source: str) -> int:
    """Count jobs whose ``search_filters->>'source'`` equals ``source``.

    Drives "first run" detection per scraper source, so an initial-import cap
    only triggers when *this* scraper has never saved a job — not merely when
    the table is globally empty (manual jobs must not suppress it).

    Args:
        db: Active async DB session.
        source: The scraper source id (e.g. ``"jobmaster"``).

    Returns:
        The number of jobs previously saved by this source.
    """
    stmt = select(func.count()).select_from(Job).where(
        Job.search_filters["source"].astext == source
    )
    return int((await db.execute(stmt)).scalar_one())
