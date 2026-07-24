import pytest
from pydantic import ValidationError

from app.schemas import (
    OperationUpdate,
    PurchaseMaterialCreate,
    PurchaseRecordUpdate,
    StockMaterialCreate,
)

IMAGE_ID = "01900000-0000-7000-8000-000000000001"


def purchase_material_payload() -> dict[str, object]:
    return {
        "material_code": "",
        "category": "",
        "name": "接触器",
        "model_spec": "CJX2-1810",
        "unit_id": 1,
        "planned_qty": "2",
        "usage": "设备检修",
        "image_ids": [IMAGE_ID],
    }


def purchase_record_payload() -> dict[str, object]:
    return {
        "plan_date": "2026-07-22",
        "material_code": "",
        "material_name": "接触器",
        "model_spec": "CJX2-1810",
        "unit_id": 1,
        "actual_demand_person": "张三",
        "purchase_responsible": "李四",
        "purchase_qty": "2",
        "usage": "设备检修",
        "image_ids": [IMAGE_ID],
        "status": "已申购",
        "version": 1,
    }


def operation_update_payload() -> dict[str, object]:
    return {
        "version": 1,
        "operation_type": "INBOUND",
        "occurred_at": "2026-07-22T09:00:00+08:00",
        "source_type": "MANUAL",
        "lines": [{"stock_material_id": 1, "quantity": "2"}],
    }


def test_request_models_accept_valid_validator_values() -> None:
    stock = StockMaterialCreate.model_validate(
        {
            "name": "接触器",
            "model_spec": "CJX2-1810",
            "unit_id": 1,
            "image_ids": [IMAGE_ID],
        }
    )
    purchase_material = PurchaseMaterialCreate.model_validate(purchase_material_payload())
    purchase_record = PurchaseRecordUpdate.model_validate(purchase_record_payload())
    operation = OperationUpdate.model_validate(operation_update_payload())

    assert stock.image_ids == [IMAGE_ID]
    assert purchase_material.image_ids == [IMAGE_ID]
    assert purchase_material.material_code is None
    assert purchase_material.category is None
    assert purchase_material.status.value == "正常"
    assert purchase_record.image_ids == [IMAGE_ID]
    assert purchase_record.material_code is None
    assert operation.lines[0].stock_material_id == 1


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            StockMaterialCreate,
            {
                "name": "接触器",
                "model_spec": "CJX2-1810",
                "unit_id": 1,
                "image_ids": [IMAGE_ID, IMAGE_ID],
            },
        ),
        (
            PurchaseMaterialCreate,
            {**purchase_material_payload(), "image_ids": [IMAGE_ID, IMAGE_ID]},
        ),
        (
            PurchaseRecordUpdate,
            {**purchase_record_payload(), "image_ids": [IMAGE_ID, IMAGE_ID]},
        ),
    ],
)
def test_request_models_reject_duplicate_images(
    model: type[StockMaterialCreate | PurchaseMaterialCreate | PurchaseRecordUpdate],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="image_ids contains duplicates"):
        model.model_validate(payload)


def test_operation_update_rejects_duplicate_materials() -> None:
    payload = operation_update_payload()
    payload["lines"] = [
        {"stock_material_id": 1, "quantity": "2"},
        {"stock_material_id": 1, "quantity": "3"},
    ]

    with pytest.raises(ValidationError, match="one operation may only contain a material once"):
        OperationUpdate.model_validate(payload)


def test_operation_update_requires_timezone() -> None:
    payload = operation_update_payload()
    payload["occurred_at"] = "2026-07-22T09:00:00"

    with pytest.raises(ValidationError, match="occurred_at must include a timezone"):
        OperationUpdate.model_validate(payload)


def test_purchase_material_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        PurchaseMaterialCreate.model_validate({**purchase_material_payload(), "status": "已取消"})
