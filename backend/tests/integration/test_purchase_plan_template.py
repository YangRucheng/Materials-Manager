from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.core.constants import SHANGHAI
from app.core.database import SessionLocal
from app.models import PurchaseMaterial, PurchasePlanTemplate
from tests.conftest import auth_headers, create_stock

BASE = "/api/v1/purchase-plan-templates"


async def upload_image(client: AsyncClient, headers: dict[str, str]) -> str:
    source = BytesIO()
    Image.new("RGB", (24, 16), "blue").save(source, format="PNG")
    response = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("motor.png", source.getvalue(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def create_template(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    code: str | None = None,
    category: str = "备品备件",
    stock_material_id: int | None = None,
    planned_qty: str = "5",
    image_ids: list[str] | None = None,
    purchase_responsible: str = "李工",
) -> dict[str, object]:
    response = await client.post(
        BASE,
        headers=headers,
        json={
            "material_code": code,
            "category": category,
            "name": name,
            "model_spec": "M60-2P 5A",
            "unit_name": "个",
            "actual_demand_person": "车间员工张三",
            "purchase_responsible": purchase_responsible,
            "planned_qty": planned_qty,
            "usage": "控制柜检修",
            "subitem_no": "01-01",
            "remark": "周期性模板",
            "stock_material_id": stock_material_id,
            "image_ids": image_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["planned_qty"] == planned_qty
    assert result["purchase_responsible"] == purchase_responsible
    assert result["category"] == category
    return result


@pytest.mark.asyncio
async def test_template_crud(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    created = await create_template(client, headers, "模板A", code="TPL-CRUD-1")

    detail = await client.get(f"{BASE}/{created['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "模板A"

    listing = await client.get(BASE, headers=headers, params={"name": "模板A"})
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1

    updated = await client.patch(
        f"{BASE}/{created['id']}",
        headers=headers,
        json={
            "material_code": "TPL-CRUD-2",
            "category": "工具",
            "name": "模板A改",
            "model_spec": "M60-2P 5A",
            "unit_name": "个",
            "actual_demand_person": "车间员工张三",
            "purchase_responsible": "王工",
            "planned_qty": "8",
            "usage": "控制柜检修",
            "image_ids": [],
            "version": created["version"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "模板A改"
    assert updated.json()["purchase_responsible"] == "王工"
    assert updated.json()["version"] == created["version"] + 1

    deleted = await client.delete(
        f"{BASE}/{created['id']}",
        headers={**headers, "If-Match": str(updated.json()["version"])},
    )
    assert deleted.status_code == 204, deleted.text

    gone = await client.get(f"{BASE}/{created['id']}", headers=headers)
    assert gone.status_code == 400
    assert gone.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_template_permissions(client: AsyncClient) -> None:
    readonly = await auth_headers(client, "readonly")
    created = await create_template(client, await auth_headers(client, "purchase"), "权限模板")

    payload = {
        "name": "越权",
        "model_spec": "X",
        "unit_name": "个",
        "planned_qty": "1",
        "usage": "x",
        "image_ids": [],
    }
    assert (await client.post(BASE, headers=readonly, json=payload)).status_code == 403
    assert (
        await client.patch(
            f"{BASE}/{created['id']}",
            headers=readonly,
            json={**payload, "version": created["version"]},
        )
    ).status_code == 403
    assert (
        await client.delete(f"{BASE}/{created['id']}", headers=readonly)
    ).status_code == 403
    assert (
        await client.post(f"{BASE}/{created['id']}/generate", headers=readonly)
    ).status_code == 403


@pytest.mark.asyncio
async def test_template_version_conflict(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    created = await create_template(client, headers, "版本冲突模板")

    payload = {
        "name": "版本冲突模板",
        "model_spec": "M60-2P 5A",
        "unit_name": "个",
        "planned_qty": "5",
        "usage": "控制柜检修",
        "image_ids": [],
        "version": created["version"] + 1,
    }
    response = await client.patch(f"{BASE}/{created['id']}", headers=headers, json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_generate_copies_full_plan_and_keeps_template(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    admin_headers = await auth_headers(client, "admin")
    stock_id = await create_stock(client, admin_headers)
    file_id = await upload_image(client, admin_headers)
    template = await create_template(
        client,
        headers,
        "自动生成模板",
        code="TPL-GEN-1",
        category="消耗物资",
        stock_material_id=stock_id,
        planned_qty="12",
        image_ids=[file_id],
    )
    template_id = int(template["id"])
    today = datetime.now(SHANGHAI).date()

    response = await client.post(f"{BASE}/{template_id}/generate", headers=headers)
    assert response.status_code == 200, response.text
    material = response.json()
    assert material["plan_date"] == today.isoformat()
    assert material["plan_no"].startswith(f"PLAN-{today:%Y%m%d}-")
    assert material["status"] == "正常"
    assert material["name"] == "自动生成模板"
    assert material["model_spec"] == "M60-2P 5A"
    assert material["unit_name"] == "个"
    assert material["planned_qty"] == "12"
    assert material["actual_demand_person"] == "车间员工张三"
    assert material["purchase_responsible"] == "李工"
    assert material["category"] == "消耗物资"
    assert material["usage"] == "控制柜检修"
    assert material["subitem_no"] == "01-01"
    assert material["remark"] == "周期性模板"
    assert material["material_code"] == "TPL-GEN-1"
    assert material["stock_material_id"] == stock_id
    assert [image["id"] for image in material["images"]] == [file_id]

    # 模板仍存在且内容未变
    detail = await client.get(f"{BASE}/{template_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "自动生成模板"
    assert detail.json()["version"] == template["version"]
    assert [image["id"] for image in detail.json()["images"]] == [file_id]

    async with SessionLocal() as session:
        template_row = await session.get(PurchasePlanTemplate, template_id)
        assert template_row is not None
        material_row = await session.get(PurchaseMaterial, int(material["id"]))
        assert material_row is not None
        assert material_row.plan_date == today
        assert material_row.status.value == "正常"
        assert {link.file_id for link in material_row.images} == {file_id}


@pytest.mark.asyncio
async def test_generate_twice_creates_distinct_plans(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    template = await create_template(client, headers, "重复生成模板")

    first = await client.post(f"{BASE}/{template['id']}/generate", headers=headers)
    second = await client.post(f"{BASE}/{template['id']}/generate", headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["plan_no"] != second.json()["plan_no"]

    async with SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(PurchaseMaterial).where(
                        PurchaseMaterial.plan_no.in_(
                            [first.json()["plan_no"], second.json()["plan_no"]]
                        )
                    )
                )
            ).all()
        )
        assert len(rows) == 2
