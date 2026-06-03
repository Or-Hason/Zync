"""Test helpers: in-memory builders for valid PDF and DOCX fixtures."""

from __future__ import annotations

import io

from docx import Document


def _escape_pdf_text(value: str) -> str:
    """Escape a string for inclusion in a PDF text-showing operator.

    Args:
        value: Raw line of text.

    Returns:
        The escaped string safe for a ``(...) Tj`` operator.
    """
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[str]) -> bytes:
    """Build a minimal, valid single-page PDF containing the given text lines.

    The output has a correct cross-reference table so pdfminer.six extracts the
    text deterministically without needing an external PDF library.

    Args:
        lines: Text lines to render on the page.

    Returns:
        Complete PDF file bytes.
    """
    text_ops = "BT /F1 14 Tf 72 760 Td 16 TL\n"
    for line in lines:
        text_ops += f"({_escape_pdf_text(line)}) Tj T*\n"
    text_ops += "ET"
    stream = text_ops.encode("latin-1")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += ("%010d 00000 n \n" % offset).encode("latin-1")
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_pos,
    )
    return out


def make_docx(lines: list[str]) -> bytes:
    """Build a valid DOCX (OOXML) document containing the given paragraphs.

    Args:
        lines: Paragraph texts to add.

    Returns:
        Complete DOCX file bytes.
    """
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_fake_exe() -> bytes:
    """Return bytes resembling a Windows executable (for spoof-rejection tests).

    Returns:
        Bytes beginning with the ``MZ`` DOS header.
    """
    return b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64
