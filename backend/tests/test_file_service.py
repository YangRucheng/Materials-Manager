from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.core.config import settings
from app.services.file_service import save_image


class FailingCommitSession:
    rolled_back = False

    def add(self, item: object) -> None:
        pass

    async def scalars(self, statement: object) -> EmptyScalarResult:
        return EmptyScalarResult()

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.rolled_back = True


class EmptyScalarResult:
    def all(self) -> list[object]:
        return []


@pytest.mark.asyncio
async def test_upload_removes_disk_file_when_database_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    source = io.BytesIO()
    Image.new("RGB", (16, 12), "red").save(source, format="PNG")
    upload = UploadFile(
        file=io.BytesIO(source.getvalue()),
        filename="source.png",
        headers=Headers({"content-type": "image/png"}),
    )
    session = FailingCommitSession()

    with pytest.raises(RuntimeError, match="commit failed"):
        await save_image(session, upload)  # type: ignore[arg-type]

    assert session.rolled_back is True
    assert list(settings.upload_dir.glob("*.png")) == []
