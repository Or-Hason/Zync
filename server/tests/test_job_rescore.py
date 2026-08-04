"""Tests for ``rescore_job`` — the job_scores UPSERT path.

The architectural promise of the ``job_scores`` bridging table is that scoring
one job with several CVs never duplicates the job row: the first score for a CV
inserts, a repeat score for the *same* CV updates in place, and a *different* CV
adds a second score row. Those three invariants are what these tests pin down,
alongside the guard clauses and the status side-effect.
"""

from __future__ import annotations

import pytest

from app.models.job import Job
from app.services.job_pipeline import (
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    KIND_SCORED,
    rescore_job,
)
from tests._job_rescore import (
    FakeRescoreSession,
    RescoreGemini,
    make_job,
    make_resume,
    make_score,
    result,
)

pytestmark = pytest.mark.asyncio


class TestGuardClauses:
    """Every early return happens before any write."""

    async def test_missing_job_returns_unavailable(self) -> None:
        from uuid import uuid4

        session = FakeRescoreSession(job=None, active_resume=make_resume())
        gemini = RescoreGemini(result())

        outcome = await rescore_job(db=session, gemini=gemini, job_id=uuid4())

        assert outcome.kind == KIND_GEMINI_UNAVAILABLE
        assert outcome.job is None
        assert gemini.calls == []
        assert session.scores == []

    async def test_no_active_resume_skips_gemini(self) -> None:
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=None)
        gemini = RescoreGemini(result())

        outcome = await rescore_job(db=session, gemini=gemini, job_id=job.id)

        assert outcome.kind == KIND_NO_ACTIVE_RESUME
        assert outcome.job is job
        assert gemini.calls == []
        assert session.scores == []

    async def test_unconfigured_gemini_skips_scoring(self) -> None:
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=make_resume())
        gemini = RescoreGemini(result(), configured=False)

        outcome = await rescore_job(db=session, gemini=gemini, job_id=job.id)

        assert outcome.kind == KIND_GEMINI_UNCONFIGURED
        assert gemini.calls == []
        assert session.scores == []

    async def test_rate_limited_gemini_writes_nothing(self) -> None:
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=make_resume())
        gemini = RescoreGemini(unavailable=True)

        outcome = await rescore_job(db=session, gemini=gemini, job_id=job.id)

        assert outcome.kind == KIND_GEMINI_UNAVAILABLE
        assert gemini.calls  # Gemini was reached, then raised.
        assert session.scores == []


class TestUpsertSemantics:
    """One score row per (job, resume) — insert, update in place, never append."""

    async def test_first_score_inserts_row(self) -> None:
        job = make_job()
        resume = make_resume()
        session = FakeRescoreSession(job=job, active_resume=resume)

        outcome = await rescore_job(
            db=session, gemini=RescoreGemini(result(78)), job_id=job.id
        )

        assert outcome.kind == KIND_SCORED
        assert outcome.score.match_score == 78
        assert outcome.scored_by_resume_id == resume.id
        assert len(session.scores) == 1
        stored = session.scores[0]
        assert stored.job_id == job.id
        assert stored.resume_id == resume.id
        assert stored.match_score == 78

    async def test_same_cv_updates_in_place(self) -> None:
        """A repeat score for the same CV overwrites — it does not accumulate."""
        job = make_job()
        resume = make_resume()
        existing = make_score(job.id, resume.id, 50)
        session = FakeRescoreSession(
            job=job, active_resume=resume, scores=[existing]
        )

        await rescore_job(db=session, gemini=RescoreGemini(result(91)), job_id=job.id)

        assert len(session.scores) == 1, "UPSERT appended instead of updating"
        assert session.scores[0] is existing  # same row mutated
        assert existing.match_score == 91
        assert existing.score_details["rationale"] == (
            "Strong overlap on backend skills."
        )

    async def test_second_cv_adds_row_without_touching_the_first(self) -> None:
        """The whole point of the bridging table: N CVs, one job row."""
        job = make_job()
        other_resume = make_resume("Older CV")
        active = make_resume("Active CV")
        other_score = make_score(job.id, other_resume.id, 25)
        session = FakeRescoreSession(
            job=job, active_resume=active, scores=[other_score]
        )

        await rescore_job(db=session, gemini=RescoreGemini(result(88)), job_id=job.id)

        assert len(session.scores) == 2
        assert other_score.match_score == 25  # untouched
        added = [s for s in session.scores if s.resume_id == active.id]
        assert len(added) == 1
        assert added[0].match_score == 88

    async def test_job_row_is_never_duplicated(self) -> None:
        """No Job is ever added to the session — the old design cloned rows here."""
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(result(88)), job_id=job.id)

        assert not [obj for obj in session.added if isinstance(obj, Job)]

    async def test_failed_parse_writes_no_score(self) -> None:
        """Gemini returning ``None`` must leave job_scores untouched."""
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        outcome = await rescore_job(
            db=session, gemini=RescoreGemini(None), job_id=job.id
        )

        assert outcome.kind == KIND_SCORED
        assert outcome.score is None
        assert outcome.scored_by_resume_id is None
        assert session.scores == []

    async def test_score_details_are_persisted(self) -> None:
        job = make_job()
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(result(78)), job_id=job.id)

        details = session.scores[0].score_details
        assert details["rationale"] == "Strong overlap on backend skills."
        assert details["matched_skills"] == ["Python", "FastAPI"]
        assert details["missing_skills"] == ["Go"]


class TestStatusSideEffect:
    """Re-scoring drives auto-managed statuses only."""

    async def test_low_score_auto_rejects(self) -> None:
        job = make_job(status="not_applied")
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(result(20)), job_id=job.id)

        assert job.status == "auto_rejected"

    async def test_recovered_score_clears_auto_rejection(self) -> None:
        job = make_job(status="auto_rejected")
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(result(85)), job_id=job.id)

        assert job.status == "not_applied"

    @pytest.mark.parametrize("user_status", ["applied", "hr_interview", "accepted"])
    async def test_user_set_status_is_preserved(self, user_status: str) -> None:
        """A re-score must never undo progress the user recorded by hand."""
        job = make_job(status=user_status)
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(result(10)), job_id=job.id)

        assert job.status == user_status

    async def test_failed_parse_leaves_status_alone(self) -> None:
        job = make_job(status="not_applied")
        session = FakeRescoreSession(job=job, active_resume=make_resume())

        await rescore_job(db=session, gemini=RescoreGemini(None), job_id=job.id)

        assert job.status == "not_applied"
