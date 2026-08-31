from __future__ import annotations

import asyncio

import pytest

from app.main import app
from app.mcp_server import _build_path, _operation_catalog, operation_describe, operations_list


def test_operation_catalog_exposes_management_apis_only() -> None:
    catalog = _operation_catalog()

    assert catalog
    assert any(item["path"] == "/api/v1/stock-materials" for item in catalog.values())
    assert any(item["path"] == "/api/v1/purchase-materials" for item in catalog.values())
    assert all(not item["path"].startswith("/api/v1/agent/database") for item in catalog.values())
    assert all(not item["path"].startswith("/api/v1/mini-program/") for item in catalog.values())
    assert all(item["path"] != "/api/v1/auth/login" for item in catalog.values())
    assert all(item["path"] != "/api/v1/auth/refresh" for item in catalog.values())


def test_operation_list_and_describe_use_openapi_contract() -> None:
    listed = asyncio.run(operations_list(keyword="stock"))

    assert listed["count"] > 0
    operation_id = listed["operations"][0]["operation_id"]
    described = asyncio.run(operation_describe(operation_id))
    assert described["operation_id"] == operation_id
    assert described["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    referenced_names = {
        reference.removeprefix("#/components/schemas/")
        for reference in _collect_references(described)
    }
    assert referenced_names <= described["schemas"].keys()


def test_build_path_requires_exact_parameters() -> None:
    assert _build_path("/api/v1/items/{item_id}", {"item_id": "a/b"}) == (
        "/api/v1/items/a%2Fb"
    )
    with pytest.raises(ValueError, match="缺少路径参数"):
        _build_path("/api/v1/items/{item_id}", {})
    with pytest.raises(ValueError, match="未定义"):
        _build_path("/api/v1/items/{item_id}", {"item_id": 1, "other": 2})


def test_mcp_mount_is_not_part_of_business_openapi() -> None:
    assert "/api/v1/mcp" not in app.openapi()["paths"]


def _collect_references(value: object) -> set[str]:
    if isinstance(value, dict):
        references = {
            item for key, item in value.items() if key == "$ref" and isinstance(item, str)
        }
        for child in value.values():
            references.update(_collect_references(child))
        return references
    if isinstance(value, list):
        references: set[str] = set()
        for child in value:
            references.update(_collect_references(child))
        return references
    return set()
