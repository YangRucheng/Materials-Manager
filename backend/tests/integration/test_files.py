from __future__ import annotations

import io
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import FileObject
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_uploaded_image_is_reencoded_as_png(client: AsyncClient) -> None:
    headers = await auth_headers(client, "warehouse")
    source = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(source, format="JPEG", exif=b"Exif\x00\x00metadata")
    response = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("source.jpg", source.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert UUID(body["id"]).version == 7
    assert "url" not in body
    assert body["mime_type"] == "image/png"
    image_url = f'/api/v1/files/images/{body["id"]}'
    downloaded = await client.get(image_url)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"\x89PNG\r\n\x1a\n")
    expected_cache = "public, max-age=86400, s-maxage=2592000"
    assert downloaded.headers["cache-control"] == expected_cache

    preview = await client.get(image_url, params={"size": 16})
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/webp")
    assert preview.headers["cache-control"] == expected_cache
    with Image.open(io.BytesIO(preview.content)) as image:
        assert image.size == (16, 12)
    assert not (settings.upload_dir / ".previews").exists()

    linked = await client.post(
        "/api/v1/stock-materials",
        headers=headers,
        json={
            "name": "带图物资",
            "model_spec": "IMG-1",
            "unit_id": 1,
            "remark": None,
            "image_ids": [body["id"]],
        },
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["images"][0]["id"] == body["id"]

    invalid_preview = await client.get(image_url, params={"size": 15})
    assert invalid_preview.status_code == 422

    async with SessionLocal() as session:
        persisted_id = await session.scalar(
            select(FileObject.id).where(FileObject.id == body["id"])
        )
    assert persisted_id == body["id"]


@pytest.mark.asyncio
async def test_image_upload_still_requires_authentication(client: AsyncClient) -> None:
    source = io.BytesIO()
    Image.new("RGB", (16, 12), "blue").save(source, format="PNG")

    response = await client.post(
        "/api/v1/files/images",
        files={"file": ("source.png", source.getvalue(), "image/png")},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_super_admin_can_report_and_cleanup_orphan_files(client: AsyncClient) -> None:
    warehouse_headers = await auth_headers(client, "warehouse")
    admin_headers = await auth_headers(client, "admin")
    source = io.BytesIO()
    Image.new("RGB", (16, 12), "green").save(source, format="PNG")
    uploaded = await client.post(
        "/api/v1/files/images",
        headers=warehouse_headers,
        files={"file": ("orphan.png", source.getvalue(), "image/png")},
    )
    file_id = uploaded.json()["id"]
    untracked_id = "01900000-0000-7000-8000-000000000999"
    (settings.upload_dir / f"{untracked_id}.png").write_bytes(source.getvalue())

    forbidden = await client.get(
        "/api/v1/files/images/orphans?older_than_hours=0", headers=warehouse_headers
    )
    assert forbidden.status_code == 403

    report = await client.get(
        "/api/v1/files/images/orphans?older_than_hours=0", headers=admin_headers
    )
    assert report.status_code == 200, report.text
    assert [item["id"] for item in report.json()["unreferenced_records"]] == [file_id]
    assert report.json()["untracked_file_names"] == [f"{untracked_id}.png"]
    assert report.json()["missing_file_ids"] == []

    cleaned = await client.delete(
        "/api/v1/files/images/orphans?older_than_hours=0", headers=admin_headers
    )
    assert cleaned.status_code == 200, cleaned.text
    assert cleaned.json()["deleted_record_ids"] == [file_id]
    assert set(cleaned.json()["deleted_file_names"]) == {
        f"{file_id}.png",
        f"{untracked_id}.png",
    }
    assert not (settings.upload_dir / f"{file_id}.png").exists()
    assert not (settings.upload_dir / f"{untracked_id}.png").exists()
