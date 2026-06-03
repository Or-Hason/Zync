"""Resume upload, listing, and update endpoints.

PII rule (DESIGN.md): logs reference only ``resume_id`` and ``version_name`` —
never ``raw_text``, ``email``, ``phone``, ``full_name``, or original filenames.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeListItem, ResumeRead, ResumeUpdate
from app.services.file_storage import save_upload
from app.services.ollama_client import OllamaClient, get_ollama_client
from app.services.resume_parser import sanitize_structured_data
from app.services.text_extraction import (
    TextExtractionError,
    UnsupportedFileTypeError,
    detect_file_kind,
    extract_text,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger(__name__)

# Read chunk size while enforcing the upload cap without buffering the whole
# stream up front.
_READ_CHUNK_BYTES = 64 * 1024


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload fully, rejecting it once it exceeds the size cap.

    Args:
        file: The incoming multipart file.
        max_bytes: Maximum number of bytes permitted.

    Returns:
        The complete file contents.

    Raises:
        HTTPException: 413 if the stream exceeds ``max_bytes``; 400 if empty.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    return b"".join(chunks)


@router.post(
    "/upload",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF/DOCX resume and parse it with Ollama",
)
async def upload_resume(
    file: UploadFile = File(...),
    version_name: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
) -> ResumeRead:
    """Accept a resume file, parse it into structured data, and persist it.

    Args:
        file: Multipart PDF or DOCX upload.
        version_name: Optional human-friendly label for this resume version.
        db: Injected async DB session.
        ollama: Injected async Ollama client.

    Returns:
        The created resume record (HTTP 201).

    Raises:
        HTTPException: 413 (too large), 415 (unsupported type), 422 (no text).
    """
    settings = get_settings()
    data = await _read_capped(file, settings.max_upload_size_bytes)

    try:
        kind = detect_file_kind(data)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and DOCX resumes are accepted.",
        ) from exc

    try:
        raw_text = extract_text(data, kind)
    except TextExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any text from the uploaded file.",
        ) from exc

    file_path = await save_upload(data, kind)
    raw_structured = await ollama.parse_resume(raw_text, file.filename or "")
    structured = sanitize_structured_data(raw_structured)

    resolved_version = (version_name or "").strip() or _fallback_version_name(
        file.filename, structured.full_name
    )

    resume = Resume(
        id=uuid4(),
        version_name=resolved_version,
        target_role=structured.target_role,
        structured_data=structured.model_dump(),
        raw_text=raw_text,
        file_path=str(file_path),
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    logger.info(
        "Resume parsed and stored",
        extra={"resume_id": str(resume.id), "version_name": resume.version_name},
    )
    return ResumeRead.model_validate(resume)


def _fallback_version_name(filename: str | None, full_name: str | None) -> str:
    """Derive a default version label when the client supplies none.

    Args:
        filename: Original upload filename (may be ``None``).
        full_name: Parsed candidate name (may be ``None``).

    Returns:
        A non-empty version label.
    """
    if filename:
        stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0].strip()
        if stem:
            return stem
    return full_name or "Untitled Resume"


@router.get(
    "",
    response_model=list[ResumeListItem],
    summary="List resumes, newest first",
)
async def list_resumes(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[ResumeListItem]:
    """Return resume summaries ordered by ``created_at`` descending.

    Args:
        limit: Maximum rows to return (1–200).
        offset: Number of rows to skip for pagination.
        db: Injected async DB session.

    Returns:
        A list of lightweight resume summaries.
    """
    capped_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    stmt = (
        select(Resume)
        .order_by(Resume.created_at.desc())
        .limit(capped_limit)
        .offset(safe_offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ResumeListItem.model_validate(row) for row in rows]


@router.put(
    "/{resume_id}",
    response_model=ResumeRead,
    summary="Update a resume's structured data and/or version name",
)
async def update_resume(
    resume_id: UUID,
    payload: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    """Persist user corrections to a resume record.

    Args:
        resume_id: Target resume primary key.
        payload: Partial update with optional ``version_name`` /
            ``structured_data``.
        db: Injected async DB session.

    Returns:
        The updated resume record.

    Raises:
        HTTPException: 404 if no resume matches ``resume_id``.
    """
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )

    if payload.version_name is not None:
        trimmed = payload.version_name.strip()
        if trimmed:
            resume.version_name = trimmed

    if payload.structured_data is not None:
        resume.structured_data = payload.structured_data.model_dump()
        resume.target_role = payload.structured_data.target_role

    await db.flush()
    await db.refresh(resume)

    logger.info(
        "Resume updated",
        extra={"resume_id": str(resume.id), "version_name": resume.version_name},
    )
    return ResumeRead.model_validate(resume)
