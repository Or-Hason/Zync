"""Tests for best-effort upload-file deletion (resume cleanup on delete)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.file_storage import delete_upload


class TestDeleteUpload:
    """``delete_upload`` removes files and degrades gracefully."""

    @pytest.mark.asyncio
    async def test_removes_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "resume.pdf"
        target.write_bytes(b"%PDF-1.4 fake")

        result = await delete_upload(str(target))

        assert result is True
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_missing_file_is_success(self, tmp_path: Path) -> None:
        target = tmp_path / "already-gone.pdf"

        result = await delete_upload(str(target))

        assert result is True

    @pytest.mark.asyncio
    async def test_blank_path_is_noop(self) -> None:
        assert await delete_upload("") is True
