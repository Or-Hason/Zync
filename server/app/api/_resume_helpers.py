"""Private helpers for the resume endpoints.

Extracted from ``resumes.py`` to keep the router module under the 300-LOC limit.
These functions are not part of the public API surface; call them only from
``resumes.py``.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

# Read chunk size while enforcing the upload cap without buffering the whole
# stream up front.
_READ_CHUNK_BYTES = 64 * 1024


async def read_capped(file: UploadFile, max_bytes: int) -> bytes:
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


def fallback_version_name(filename: str | None, full_name: str | None) -> str:
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
