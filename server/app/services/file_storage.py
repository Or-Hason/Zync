"""Async persistence of uploaded resume files to the configured upload dir."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import aiofiles

from app.core.config import get_settings
from app.services.text_extraction import FileKind

logger = logging.getLogger(__name__)

# Maps the detected file kind to its on-disk extension.
_KIND_EXTENSIONS: dict[FileKind, str] = {"pdf": "pdf", "docx": "docx"}


async def save_upload(data: bytes, kind: FileKind) -> Path:
    """Persist uploaded bytes under a random filename and return its path.

    The stored name is a fresh UUID, never the client-supplied filename, which
    avoids path-traversal and PII leakage through file names.

    Args:
        data: Raw file bytes to write.
        kind: Detected file kind, used to choose the extension.

    Returns:
        The absolute path of the written file.
    """
    settings = get_settings()
    upload_dir = settings.upload_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    destination = upload_dir / f"{uuid4()}.{_KIND_EXTENSIONS[kind]}"
    async with aiofiles.open(destination, "wb") as handle:
        await handle.write(data)

    logger.info("Stored resume upload", extra={"kind": kind, "bytes": len(data)})
    return destination.resolve()


async def delete_upload(file_path: str) -> bool:
    """Remove a stored upload file from disk (best-effort).

    Deletion is best-effort: a missing or already-removed file is treated as
    success, and any filesystem error is logged but never propagated, so resume
    deletion (the DB row removal) is never blocked by orphaned-file cleanup.

    Args:
        file_path: Absolute path to the stored upload file.

    Returns:
        ``True`` if the file no longer exists after the call, ``False`` if it
        could not be removed.
    """
    if not file_path:
        return True

    target = Path(file_path)
    try:
        target.unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Failed to delete resume upload file from disk",
            extra={"path": target.name},
        )
        return False

    logger.info("Deleted resume upload file", extra={"path": target.name})
    return True
