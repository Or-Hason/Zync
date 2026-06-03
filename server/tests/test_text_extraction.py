"""Tests for byte-level MIME detection and text extraction."""

from __future__ import annotations

import pytest

from app.services.text_extraction import (
    MIME_DOCX,
    TextExtractionError,
    UnsupportedFileTypeError,
    detect_file_kind,
    extract_text,
)
from tests.helpers import make_docx, make_fake_exe, make_pdf


class TestDetectFileKind:
    """MIME validation is driven by file bytes, not the extension."""

    def test_valid_pdf_detected(self, pdf_bytes: bytes) -> None:
        assert detect_file_kind(pdf_bytes) == "pdf"

    def test_valid_docx_detected(self, docx_bytes: bytes) -> None:
        assert detect_file_kind(docx_bytes) == "docx"

    def test_spoofed_executable_rejected(self, exe_bytes: bytes) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            detect_file_kind(exe_bytes)

    def test_plain_zip_without_docx_structure_rejected(self) -> None:
        # A bare ZIP (no word/document.xml) must not pass as DOCX.
        bare_zip = b"PK\x03\x04" + b"\x00" * 40
        with pytest.raises(UnsupportedFileTypeError):
            detect_file_kind(bare_zip)

    def test_plain_text_rejected(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            detect_file_kind(b"just some plain text, definitely not a resume file")


class TestExtractText:
    """Raw text extraction for each supported format."""

    def test_extract_pdf_text(self) -> None:
        pdf = make_pdf(["Alice Cooper", "Data Scientist"])
        text = extract_text(pdf, "pdf")
        assert "Alice Cooper" in text
        assert "Data Scientist" in text

    def test_extract_docx_text(self) -> None:
        docx = make_docx(["Bob Stone", "DevOps Lead"])
        text = extract_text(docx, "docx")
        assert "Bob Stone" in text
        assert "DevOps Lead" in text

    def test_empty_pdf_raises(self) -> None:
        empty_pdf = make_pdf([])
        with pytest.raises(TextExtractionError):
            extract_text(empty_pdf, "pdf")

    def test_corrupt_docx_raises(self) -> None:
        with pytest.raises(TextExtractionError):
            extract_text(make_fake_exe(), "docx")


def test_docx_mime_constant_is_ooxml() -> None:
    assert MIME_DOCX.endswith("wordprocessingml.document")
