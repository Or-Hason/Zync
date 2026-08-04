"""Fakes for the ``rescore_job`` tests.

Not collected by pytest (no ``test_`` prefix). The session double is richer than
:class:`tests._job_pipeline.FakeJobSession` because the re-score path issues a
*filtered* ``SELECT`` on ``job_scores`` — the UPSERT has to find the existing
(job, resume) row or miss it. The fake therefore reads the statement's bound
parameters instead of ignoring the WHERE clause, so a broken filter shows up as
a failing test rather than a silent always-hit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.models.job import Job
from app.models.job_score import JobScore
from app.models.resume import Resume
from app.schemas.job import ScoreResult
from app.services.gemini_client import GeminiUnavailableError


class _Rows:
    """Result double exposing the ``.scalars().all()`` / ``.first()`` surface."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_Rows":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class FakeRescoreSession:
    """In-memory async session covering every call ``rescore_job`` makes.

    Attributes:
        scores: The ``job_scores`` rows, mutated in place by the UPSERT.
        added: Every object handed to :meth:`add` — asserted on to prove the
            re-score never inserts a second ``Job`` row.
        flushes: Number of :meth:`flush` calls.
    """

    def __init__(
        self,
        *,
        job: Job | None,
        active_resume: Resume | None,
        scores: list[JobScore] | None = None,
    ) -> None:
        self._jobs: dict[UUID, Job] = {job.id: job} if job is not None else {}
        self._active = [active_resume] if active_resume is not None else []
        self.scores: list[JobScore] = list(scores or [])
        self.added: list[Any] = []
        self.flushes = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, JobScore):
            self.scores.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, _obj: Any) -> None:
        return None

    async def get(self, _model: type, pk: UUID) -> Any:
        return self._jobs.get(pk)

    async def execute(self, stmt: Any) -> _Rows:
        """Route by selected entity, honouring the WHERE clause on job_scores."""
        entity = stmt.column_descriptions[0]["name"]
        if entity == "Resume":
            return _Rows(self._active)
        if entity == "JobScore":
            params = stmt.compile().params
            job_id = params.get("job_id_1")
            resume_id = params.get("resume_id_1")
            return _Rows(
                [
                    s
                    for s in self.scores
                    if s.job_id == job_id and s.resume_id == resume_id
                ]
            )
        return _Rows([])

    async def commit(self) -> None:  # pragma: no cover - no-op in fake
        return None

    async def rollback(self) -> None:  # pragma: no cover - no-op in fake
        return None


class RescoreGemini:
    """Gemini double returning a scripted result, or raising on demand.

    Args:
        result: The :class:`ScoreResult` to return (``None`` models a parse
            failure, which must leave ``job_scores`` untouched).
        configured: Backs the ``is_configured`` property.
        unavailable: When ``True``, ``score`` raises
            :class:`GeminiUnavailableError` (all models rate-limited).
    """

    def __init__(
        self,
        result: ScoreResult | None = None,
        *,
        configured: bool = True,
        unavailable: bool = False,
    ) -> None:
        self.result = result
        self._configured = configured
        self._unavailable = unavailable
        self.calls: list[tuple[str | None, dict | None]] = []

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def score(
        self,
        job_title: str | None,
        _job_description: str | None,
        _requirements: dict | None,
        resume_structured: dict | None,
    ) -> ScoreResult | None:
        self.calls.append((job_title, resume_structured))
        if self._unavailable:
            raise GeminiUnavailableError("all models rate-limited")
        return self.result


def make_job(*, status: str = "not_applied") -> Job:
    """Build a persisted-looking job row with no scores attached.

    Args:
        status: The job's current status (drives the auto-reject assertions).

    Returns:
        A :class:`Job` with the server-default columns pre-populated, since the
        fake session never flushes them the way a real DB would.
    """
    return Job(
        id=uuid4(),
        company_name="Acme Corp",
        job_title="Senior Python Engineer",
        job_description="Own the async FastAPI platform.",
        raw_content="raw posting text",
        requirements={"skills": ["Python"]},
        source_type="manual",
        status=status,
        is_duplicate=False,
        duplicate_chance=0,
        application_options=[],
        created_at=datetime.now(timezone.utc),
    )


def make_resume(version_name: str = "Active CV") -> Resume:
    """Build an active resume row."""
    return Resume(
        id=uuid4(),
        version_name=version_name,
        target_role="Backend",
        structured_data={"skills": ["Python"]},
        raw_text="raw",
        file_path="/uploads/cv.pdf",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def make_score(job_id: UUID, resume_id: UUID, match_score: int) -> JobScore:
    """Build an existing ``job_scores`` row for the given pair."""
    return JobScore(
        id=uuid4(),
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        score_details={"rationale": "previous run"},
    )


def result(score: int = 78) -> ScoreResult:
    """Build a representative Gemini score result."""
    return ScoreResult(
        match_score=score,
        rationale="Strong overlap on backend skills.",
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Go"],
    )
