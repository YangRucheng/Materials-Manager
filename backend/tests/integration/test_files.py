from __future__ import annotations

import io
from datetime import date
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import FileObject, PurchaseRequest, PurchaseRequestLine, PurchaseRequestLineImage
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

    duplicate = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("duplicate.jpg", source.getvalue(), "image/jpeg")},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == body["id"]
    assert len(list(settings.upload_dir.glob("*.png"))) == 1

    stored_path = settings.upload_dir / f'{body["id"]}.png'
    stored_path.unlink()
    repaired = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("repair.jpg", source.getvalue(), "image/jpeg")},
    )
    assert repaired.status_code == 201, repaired.text
    assert repaired.json()["id"] == body["id"]
    assert stored_path.is_file()

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
            "unit_name": "个",
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
        file_count = await session.scalar(select(func.count()).select_from(FileObject))
    assert persisted_id == body["id"]
    assert file_count == 1


@pytest.mark.asyncio
async def test_purchase_request_line_image_is_never_treated_as_orphan(
    client: AsyncClient,
) -> None:
    """仅被申购记录行引用的图片：不算孤儿、不能被单删（回归 20260810 行级镜像表）。"""
    warehouse_headers = await auth_headers(client, "warehouse")
    admin_headers = await auth_headers(client, "admin")
    source = io.BytesIO()
    Image.new("RGB", (16, 12), "purple").save(source, format="PNG")
    uploaded = await client.post(
        "/api/v1/files/images",
        headers=warehouse_headers,
        files={"file": ("record-image.png", source.getvalue(), "image/png")},
    )
    file_id = uploaded.json()["id"]

    # 构造一条只引用该图片的申购记录行（模拟 move-to-record 后的行级镜像）。
    async with SessionLocal() as session:
        request = PurchaseRequest(purchase_date=None)
        session.add(request)
        await session.flush()
        line = PurchaseRequestLine(
            purchase_request_id=request.id,
            plan_no_snapshot="PLAN-TEST-001",
            plan_date_snapshot=date(2026, 7, 1),
            demand_department_snapshot="车间",
            material_name_snapshot="记录物资",
            model_spec_snapshot="M-1",
            unit_name_snapshot="个",
            actual_demand_person_snapshot="张三",
            purchase_responsible_snapshot="李工",
            purchase_qty="1",
            usage="测试",
        )
        session.add(line)
        await session.flush()
        session.add(
            PurchaseRequestLineImage(line_id=line.id, file_id=file_id, sort_order=0)
        )
        await session.commit()

    report = await client.get(
        "/api/v1/files/images/orphans?older_than_hours=0", headers=admin_headers
    )
    assert report.status_code == 200, report.text
    assert file_id not in [item["id"] for item in report.json()["unreferenced_records"]]

    removed = await client.delete(f"/api/v1/files/images/{file_id}", headers=warehouse_headers)
    assert removed.status_code == 409, removed.text
    assert removed.json()["code"] == "FILE_IN_USE"

    # 孤儿清理也不应删除被记录行引用的图片。
    cleaned = await client.delete(
        "/api/v1/files/images/orphans?older_than_hours=0", headers=admin_headers
    )
    assert cleaned.status_code == 200, cleaned.text
    assert file_id not in cleaned.json()["deleted_record_ids"]
    assert (settings.upload_dir / f"{file_id}.png").exists()


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
