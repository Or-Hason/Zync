"""Endpoint tests for upload, list, and update with mocked boundaries."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.resume import Resume
from tests.conftest import FakeOllamaClient, FakeSession


def _make_resume(version_name: str, target_role: str | None = None) -> Resume:
    """Build a persisted-looking Resume row for list/get fixtures."""
    return Resume(
        id=uuid4(),
        version_name=version_name,
        target_role=target_role,
        structured_data={"full_name": "X", "target_role": target_role},
        raw_text="raw",
        file_path="/uploads/x.pdf",
        created_at=datetime.now(timezone.utc),
    )


class TestUpload:
    """POST /api/resumes/upload."""

    def test_valid_pdf_returns_201_with_structured_payload(
        self, client: TestClient, pdf_bytes: bytes, fake_ollama: FakeOllamaClient
    ) -> None:
        response = client.post(
            "/api/resumes/upload",
            files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
            data={"version_name": "My CV"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["version_name"] == "My CV"
        assert body["target_role"] is None
        structured = body["structured_data"]
        assert structured["full_name"] == "Jane Doe"
        # current_role is derived from the most recent (ongoing) experience.
        assert structured["current_role"] == "Senior Engineer"
        # Non-string and blank skills are dropped during sanitisation.
        assert structured["skills"] == ["Python", "FastAPI"]
        # Numeric phone is coerced to a string.
        assert structured["phone"] == "15551234567"
        # The Ollama stub received the extracted text and filename.
        assert fake_ollama.calls
        raw_text, filename = fake_ollama.calls[0]
        assert "Jane Doe" in raw_text
        assert filename == "cv.pdf"

    def test_valid_docx_returns_201(
        self, client: TestClient, docx_bytes: bytes
    ) -> None:
        response = client.post(
            "/api/resumes/upload",
            files={
                "file": (
                    "cv.docx",
                    docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert response.status_code == 201
        # No version_name supplied -> falls back to the filename stem.
        assert response.json()["version_name"] == "cv"

    def test_spoofed_executable_rejected_415(
        self, client: TestClient, exe_bytes: bytes
    ) -> None:
        response = client.post(
            "/api/resumes/upload",
            files={"file": ("malware.pdf", exe_bytes, "application/pdf")},
        )
        assert response.status_code == 415

    def test_oversized_file_rejected_413(self, client: TestClient) -> None:
        oversized = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1)
        response = client.post(
            "/api/resumes/upload",
            files={"file": ("big.pdf", oversized, "application/pdf")},
        )
        assert response.status_code == 413

    def test_empty_file_rejected_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/resumes/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400

    def test_pii_is_not_logged(
        self, client: TestClient, pdf_bytes: bytes, caplog
    ) -> None:
        with caplog.at_level(logging.INFO):
            response = client.post(
                "/api/resumes/upload",
                files={"file": ("cv.pdf", pdf_bytes, "application/pdf")},
                data={"version_name": "Safe Label"},
            )
        assert response.status_code == 201
        logged = caplog.text
        assert "jane@example.com" not in logged
        assert "15551234567" not in logged
        assert "Jane Doe" not in logged


class TestListResumes:
    """GET /api/resumes."""

    def test_returns_summaries(
        self, client: TestClient, fake_session: FakeSession
    ) -> None:
        fake_session.rows = [_make_resume("Newest", "Backend"), _make_resume("Older")]
        response = client.get("/api/resumes")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert items[0]["version_name"] == "Newest"
        assert items[0]["target_role"] == "Backend"
        # The list projection excludes structured_data.
        assert "structured_data" not in items[0]

    def test_empty_list(self, client: TestClient) -> None:
        response = client.get("/api/resumes")
        assert response.status_code == 200
        assert response.json() == []


class TestUpdateResume:
    """PUT /api/resumes/{id}."""

    def test_update_persists_structured_data(
        self, client: TestClient, fake_session: FakeSession
    ) -> None:
        resume = _make_resume("Original")
        fake_session.get_map[resume.id] = resume

        response = client.put(
            f"/api/resumes/{resume.id}",
            json={
                "version_name": "Corrected",
                "structured_data": {
                    "full_name": "Jane Q. Doe",
                    "target_role": "Staff Engineer",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["version_name"] == "Corrected"
        assert body["target_role"] == "Staff Engineer"
        assert body["structured_data"]["full_name"] == "Jane Q. Doe"
        # Denormalised column is kept in sync with structured_data.target_role.
        assert resume.target_role == "Staff Engineer"

    def test_update_missing_resume_returns_404(self, client: TestClient) -> None:
        response = client.put(
            f"/api/resumes/{uuid4()}",
            json={"version_name": "x"},
        )
        assert response.status_code == 404


class TestActiveResume:
    """GET /api/resumes/active and PUT /api/resumes/{id}/set-active."""

    def test_get_active_returns_record(
        self, client: TestClient, fake_session: FakeSession
    ) -> None:
        active = _make_resume("Active CV", "Backend")
        active.is_active = True
        fake_session.rows = [active]

        response = client.get("/api/resumes/active")
        assert response.status_code == 200
        body = response.json()
        assert body["version_name"] == "Active CV"
        assert "structured_data" in body

    def test_get_active_returns_404_when_none(self, client: TestClient) -> None:
        response = client.get("/api/resumes/active")
        assert response.status_code == 404

    def test_set_active_marks_target_and_clears_others(
        self, client: TestClient, fake_session: FakeSession
    ) -> None:
        previous = _make_resume("Old Active")
        previous.is_active = True
        target = _make_resume("New Active")
        target.is_active = False
        fake_session.get_map[target.id] = target
        # The set-active query returns the currently-active resumes.
        fake_session.rows = [previous]

        response = client.put(f"/api/resumes/{target.id}/set-active")
        assert response.status_code == 200
        assert target.is_active is True
        assert previous.is_active is False

    def test_set_active_missing_resume_returns_404(self, client: TestClient) -> None:
        response = client.put(f"/api/resumes/{uuid4()}/set-active")
        assert response.status_code == 404
