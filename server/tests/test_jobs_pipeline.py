"""Pipeline tests: blacklist, no-active-resume guard, caching, scoring."""

from __future__ import annotations

from app.services.system_advice import ADVICE_LOW_SCORE
from tests._job_pipeline import (
    SAMPLE_JOB_DESCRIPTION,
    SAMPLE_JOB_RAW,
    FakeBlacklistStore,
    FakeGemini,
    FakeJobOllama,
    FakeJobSession,
    ScoredRow,
    make_active_resume,
    make_score_result,
    pipeline_client,
)


def _scrape(
    *,
    keywords: list[str] | None = None,
    active: bool = True,
    gemini_result=...,
    gemini_configured: bool = True,
    scored_rows: list[ScoredRow] | None = None,
    body: dict | None = None,
):
    """Run one scrape request against fully stubbed dependencies.

    Returns a tuple of (response, gemini stub) so tests can assert on whether
    Gemini was actually invoked.
    """
    session = FakeJobSession()
    session.active_resumes = [make_active_resume()] if active else []
    session.scored_rows = scored_rows or []

    ollama = FakeJobOllama()
    result = make_score_result(78) if gemini_result is ... else gemini_result
    gemini = FakeGemini(result=result, configured=gemini_configured)
    store = FakeBlacklistStore(keywords)

    with pipeline_client(session, ollama, gemini, store) as client:
        response = client.post(
            "/api/jobs/scrape", json=body or {"raw_text": "any job text"}
        )
    return response, gemini, session


class TestBlacklistFiltration:
    """Filtration runs on title + description; force_score can bypass it."""

    def test_hit_without_force_returns_422_and_skips_gemini(self) -> None:
        response, gemini, session = _scrape(keywords=["python"])
        assert response.status_code == 422
        body = response.json()
        assert body["error"] == "blacklist_hit"
        assert body["matched_keyword"] == "python"
        assert body["job"]["status"] == "auto_rejected"
        assert gemini.calls == []  # Gemini must not be called on a blacklist hit.
        assert len(session.added) == 1  # auto_rejected row is persisted.

    def test_hit_with_force_proceeds_to_scoring(self) -> None:
        response, gemini, _ = _scrape(
            keywords=["python"], body={"raw_text": "x", "force_score": True}
        )
        assert response.status_code == 201
        assert gemini.calls  # scoring proceeded despite the blacklist hit.

    def test_company_description_is_never_scanned(self) -> None:
        # "logistics" appears only in company_description -> no hit -> 201.
        response, _, _ = _scrape(keywords=["logistics"])
        assert response.status_code == 201


class TestNoActiveResumeGuard:
    """Scoring requires an active resume."""

    def test_returns_400_with_saved_job(self) -> None:
        response, gemini, _ = _scrape(active=False)
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "no_active_resume"
        assert body["job"]["status"] == "not_applied"
        assert gemini.calls == []


class TestScoreCaching:
    """A >0.90 TF-IDF match to an already-scored job reuses the score."""

    def test_cache_hit_reuses_score_and_skips_gemini(self) -> None:
        cached = ScoredRow(
            "Senior Python Engineer",
            SAMPLE_JOB_DESCRIPTION,
            91,
            {
                "rationale": "cached!",
                "matched_skills": ["Python"],
                "missing_skills": [],
            },
        )
        response, gemini, _ = _scrape(scored_rows=[cached])
        assert response.status_code == 201
        body = response.json()
        assert body["score_cached"] is True
        assert body["match_score"] == 91
        assert body["rationale"] == "cached!"
        assert gemini.calls == []  # cache hit -> no Gemini call.


class TestGeminiScoring:
    """Fresh scoring sets the score, resume linkage, and advice."""

    def test_successful_score_sets_fields(self) -> None:
        response, gemini, session = _scrape()
        assert response.status_code == 201
        body = response.json()
        assert body["match_score"] == 78
        assert body["score_cached"] is False
        assert body["system_advice"] == "Strong match — recommended to apply."
        # scored_by_resume_id links the job to the active resume.
        assert body["scored_by_resume_id"] == str(session.active_resumes[0].id)
        assert gemini.calls

    def test_low_score_auto_rejects_but_returns_full_payload(self) -> None:
        response, _, _ = _scrape(gemini_result=make_score_result(25))
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "auto_rejected"
        # Full payload is still returned for the Job Card.
        assert body["match_score"] == 25
        assert body["rationale"] == "Strong overlap on backend skills."
        assert body["matched_skills"] == ["Python", "FastAPI"]
        assert body["missing_skills"] == ["Go"]
        assert body["system_advice"] == ADVICE_LOW_SCORE

    def test_gemini_failure_leaves_score_null(self) -> None:
        response, _, _ = _scrape(gemini_result=None)
        assert response.status_code == 201
        body = response.json()
        assert body["match_score"] is None
        assert body["scored_by_resume_id"] is None
        assert body["system_advice"] is not None

    def test_missing_api_key_returns_500(self) -> None:
        response, _, _ = _scrape(gemini_configured=False)
        assert response.status_code == 500


class TestContentClassificationGate:
    """Non-VALID_JOB classifications halt the pipeline without a DB insert."""

    def _scrape_classified(self, classification: str) -> tuple:
        session = FakeJobSession()
        session.active_resumes = [make_active_resume()]
        payload = {**SAMPLE_JOB_RAW, "content_classification": classification}
        ollama = FakeJobOllama(payload=payload)
        gemini = FakeGemini(result=make_score_result(78))
        store = FakeBlacklistStore()
        with pipeline_client(session, ollama, gemini, store) as client:
            response = client.post("/api/jobs/scrape", json={"raw_text": "any text"})
        return response, session

    def test_login_wall_returns_422_no_db_insert(self) -> None:
        response, session = self._scrape_classified("LOGIN_WALL")
        assert response.status_code == 422
        assert response.json()["error"] == "login_wall"
        assert not session.added

    def test_irrelevant_returns_422_no_db_insert(self) -> None:
        response, session = self._scrape_classified("IRRELEVANT")
        assert response.status_code == 422
        assert response.json()["error"] == "irrelevant_content"
        assert not session.added

    def test_insufficient_data_returns_422_no_db_insert(self) -> None:
        response, session = self._scrape_classified("INSUFFICIENT_DATA")
        assert response.status_code == 422
        assert response.json()["error"] == "insufficient_data"
        assert not session.added

    def test_valid_job_proceeds_to_scoring(self) -> None:
        response, _ = self._scrape_classified("VALID_JOB")
        assert response.status_code == 201

    def test_missing_classification_proceeds_to_scoring(self) -> None:
        """None classification is treated as valid (lenient fallback)."""
        session = FakeJobSession()
        session.active_resumes = [make_active_resume()]
        payload = {**SAMPLE_JOB_RAW, "content_classification": None}
        ollama = FakeJobOllama(payload=payload)
        gemini = FakeGemini(result=make_score_result(78))
        store = FakeBlacklistStore()
        with pipeline_client(session, ollama, gemini, store) as client:
            response = client.post("/api/jobs/scrape", json={"raw_text": "any text"})
        assert response.status_code == 201
