from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from tests.conftest import auth_headers


def build_workbook(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["状态", "编码", "名称", "记账单位名称", "型号", "其他列"])
    for row in rows:
        worksheet.append(row)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return content.getvalue()


@pytest.mark.asyncio
async def test_import_replaces_and_searches_material_code_library(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    first_import = await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={
            "file": (
                "codes.xlsx",
                build_workbook(
                    [
                        ["生效", "Y001", "交流接触器", "个", "CJX2-2510", "忽略"],
                        ["生效", "Y002", "控制电缆", "米", "KVV 4×1.5", "忽略"],
                        ["生效", "Y003", "", "箱", "", "忽略"],
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert first_import.status_code == 200, first_import.text
    assert first_import.json() == {
        "imported_count": 3,
        "blank_name_count": 1,
        "blank_model_spec_count": 1,
    }

    by_name = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"keyword": "接触器"},
    )
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["items"] == [
        {
            "id": 1,
            "material_code": "Y001",
            "name": "交流接触器",
            "model_spec": "CJX2-2510",
            "unit_name": "个",
        }
    ]

    by_model = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"keyword": "4×1.5"},
    )
    assert by_model.status_code == 200, by_model.text
    assert by_model.json()["items"][0]["material_code"] == "Y002"

    by_name_or_model = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"keyword": "接触器|4×1.5"},
    )
    assert by_name_or_model.status_code == 200, by_name_or_model.text
    assert {item["material_code"] for item in by_name_or_model.json()["items"]} == {
        "Y001",
        "Y002",
    }

    by_code = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"keyword": "Y001"},
    )
    assert by_code.status_code == 200, by_code.text
    assert by_code.json()["items"] == [
        {
            "id": 1,
            "material_code": "Y001",
            "name": "交流接触器",
            "model_spec": "CJX2-2510",
            "unit_name": "个",
        }
    ]

    combined = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"material_code": "Y00", "name": "接触器", "model_spec": "2510"},
    )
    assert combined.status_code == 200, combined.text
    assert [item["material_code"] for item in combined.json()["items"]] == ["Y001"]

    combined_or = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={
            "name": "接触器|控制电缆",
            "model_spec": "2510｜4×1.5",
            "material_code": "Y001|Y002",
        },
    )
    assert combined_or.status_code == 200, combined_or.text
    assert [item["material_code"] for item in combined_or.json()["items"]] == ["Y001", "Y002"]

    no_combined_match = await client.get(
        "/api/v1/material-code-library",
        headers=purchase_headers,
        params={"name": "接触器", "model_spec": "4×1.5"},
    )
    assert no_combined_match.status_code == 200, no_combined_match.text
    assert no_combined_match.json()["items"] == []

    replacement = await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={
            "file": (
                "replacement.xlsx",
                build_workbook([["生效", "Y999", "按钮", "个", "LA38", "忽略"]]),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert replacement.status_code == 200, replacement.text
    all_items = await client.get(
        "/api/v1/material-code-library", headers=purchase_headers, params={"page_size": 200}
    )
    assert all_items.json()["total"] == 1
    assert all_items.json()["items"][0]["material_code"] == "Y999"


@pytest.mark.asyncio
async def test_invalid_import_does_not_delete_existing_codes(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    initial = build_workbook([["生效", "Y001", "交流接触器", "个", "CJX2", ""]])
    await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={"file": ("codes.xlsx", initial, "application/octet-stream")},
    )
    duplicate = build_workbook(
        [
            ["生效", "Y002", "按钮", "个", "LA38", ""],
            ["生效", "Y002", "按钮", "个", "LA38", ""],
        ]
    )
    response = await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={"file": ("duplicate.xlsx", duplicate, "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "MATERIAL_CODE_IMPORT_DUPLICATE"
    items = await client.get("/api/v1/material-code-library", headers=purchase_headers)
    assert items.json()["total"] == 1
    assert items.json()["items"][0]["material_code"] == "Y001"


@pytest.mark.asyncio
async def test_material_code_import_requires_purchase_permission(client: AsyncClient) -> None:
    readonly_headers = await auth_headers(client, "readonly")
    response = await client.post(
        "/api/v1/material-code-library/import",
        headers=readonly_headers,
        files={
            "file": (
                "codes.xlsx",
                build_workbook([["生效", "Y001", "按钮", "个", "LA38", ""]]),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_rejects_corrupted_file(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    response = await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={
            "file": (
                "corrupted.xlsx",
                b"this is not a valid excel file",
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_EXCEL_FILE"


@pytest.mark.asyncio
async def test_import_large_file_succeeds(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    rows = [["生效", f"Y{i:04d}", f"物料{i}", "个", f"型号{i}", "忽略"] for i in range(500)]
    file_content = build_workbook(rows)
    response = await client.post(
        "/api/v1/material-code-library/import",
        headers=purchase_headers,
        files={
            "file": (
                "large.xlsx",
                file_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["imported_count"] == 500
    assert data["blank_name_count"] == 0
    assert data["blank_model_spec_count"] == 0
