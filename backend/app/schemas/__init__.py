from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.enums import (
    OperationType,
    PurchaseRequestStatus,
    Role,
    SourceType,
)

PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=1)]
NonnegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=1)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReadModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda value: format(value.normalize(), "f")},
    )


class Page[T](ReadModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class ApiError(ReadModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str


class UserRead(ReadModel):
    id: int
    username: str
    display_name: str
    role: Role
    enabled: bool
    version: int


class LoginRequest(RequestModel):
    username: NonBlank
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(ReadModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead


class UserCreate(RequestModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)]
    password: str = Field(min_length=6, max_length=128)
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    role: Role
    enabled: bool = True


class UserUpdate(RequestModel):
    username: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)]
        | None
    ) = None
    display_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: Role | None = None
    enabled: bool | None = None
    version: int


class MeasurementUnitRead(ReadModel):
    id: int
    code: str
    name: str
    decimal_places: int
    enabled: bool
    version: int


class MeasurementUnitCreate(RequestModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    decimal_places: int = Field(default=0, ge=0, le=1)
    enabled: bool = True


class MeasurementUnitUpdate(RequestModel):
    code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)] | None
    ) = None
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)] | None
    ) = None
    decimal_places: int | None = Field(default=None, ge=0, le=1)
    enabled: bool | None = None
    version: int


class FileObjectRead(ReadModel):
    id: int
    original_name: str
    url: str
    mime_type: Literal["image/png"] = "image/png"
    size_bytes: int
    width: int
    height: int


class ReplenishmentPolicyRead(ReadModel):
    minimum_qty: Decimal
    target_qty: Decimal
    enabled: bool
    version: int = 1


class ReplenishmentPolicyWrite(RequestModel):
    minimum_qty: NonnegativeQuantity
    target_qty: NonnegativeQuantity
    enabled: bool = True
    version: int | None = None

    @model_validator(mode="after")
    def validate_range(self) -> ReplenishmentPolicyWrite:
        if self.target_qty < self.minimum_qty:
            raise ValueError("target_qty must be greater than or equal to minimum_qty")
        return self


class StockMaterialBase(RequestModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_id: int
    remark: str | None = Field(default=None, max_length=1000)
    image_ids: list[int] = Field(default_factory=list, max_length=9)

    @field_validator("image_ids")
    @classmethod
    def unique_images(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("image_ids contains duplicates")
        return value


class StockMaterialCreate(StockMaterialBase):
    pass


class StockMaterialUpdate(StockMaterialBase):
    version: int


class StockMaterialRead(ReadModel):
    id: int
    name: str
    model_spec: str
    unit_id: int
    unit_name: str
    remark: str | None = None
    enabled: bool
    current_qty: Decimal
    images: list[FileObjectRead]
    replenishment_policy: ReplenishmentPolicyRead | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class InventoryBalanceRead(ReadModel):
    stock_material_id: int
    name: str
    model_spec: str
    unit_name: str
    decimal_places: int
    current_qty: Decimal
    minimum_qty: Decimal | None = None
    target_qty: Decimal | None = None
    on_order_qty: Decimal
    is_low_stock: bool
    warning_state: Literal["PENDING_PURCHASE", "ON_ORDER"] | None = None
    suggested_purchase_qty: Decimal
    updated_at: datetime


class OperationLineWrite(RequestModel):
    stock_material_id: int
    quantity: PositiveQuantity
    purchase_request_line_id: int | None = None


class OperationCreate(RequestModel):
    client_request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    occurred_at: datetime
    source_type: SourceType
    business_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    receiver_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    lines: list[OperationLineWrite] = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("lines")
    @classmethod
    def unique_materials(cls, value: list[OperationLineWrite]) -> list[OperationLineWrite]:
        ids = [line.stock_material_id for line in value]
        if len(ids) != len(set(ids)):
            raise ValueError("one operation may only contain a material once")
        return value


class OperationUpdate(RequestModel):
    version: int
    operation_type: OperationType
    occurred_at: datetime
    source_type: SourceType
    business_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    receiver_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    lines: list[OperationLineWrite] = Field(min_length=1)

    _timezone = field_validator("occurred_at")(OperationCreate.require_timezone)
    _unique = field_validator("lines")(OperationCreate.unique_materials)


class ReverseOperationRequest(RequestModel):
    client_request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class StockOperationLineRead(ReadModel):
    id: int
    stock_material_id: int
    material_name: str
    model_spec: str
    unit_name: str
    quantity: Decimal
    before_qty: Decimal
    after_qty: Decimal
    purchase_request_line_id: int | None = None


class StockOperationRead(ReadModel):
    id: int
    operation_no: str
    operation_type: OperationType
    occurred_at: datetime
    operator_name: str
    business_reason: str
    receiver_name: str | None = None
    subitem_no: str | None = None
    source_type: SourceType
    reversal_of_id: int | None = None
    purchase_request_no: str | None = None
    client_request_id: str
    lines: list[StockOperationLineRead]
    created_at: datetime
    version: int


class PurchaseMaterialBase(RequestModel):
    material_code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_id: int
    actual_demand_person: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    purchase_responsible: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    planned_qty: PositiveQuantity
    usage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    remark: str | None = Field(default=None, max_length=1000)
    stock_material_id: int | None = None
    image_ids: list[int] = Field(default_factory=list, max_length=9)

    _unique_images = field_validator("image_ids")(StockMaterialBase.unique_images)

    @field_validator("material_code", mode="before")
    @classmethod
    def empty_code_to_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class PurchaseMaterialCreate(PurchaseMaterialBase):
    pass


class PurchaseMaterialUpdate(PurchaseMaterialBase):
    version: int


class PurchaseMaterialRead(ReadModel):
    id: int
    material_code: str | None = None
    name: str
    model_spec: str
    unit_id: int
    unit_name: str
    actual_demand_person: str
    purchase_responsible: str
    planned_qty: Decimal
    usage: str
    subitem_no: str | None = None
    remark: str | None = None
    stock_material_id: int | None = None
    stock_material_name: str | None = None
    moved_to_record: bool
    enabled: bool
    images: list[FileObjectRead]
    created_at: datetime
    updated_at: datetime
    version: int


class LinkStockMaterialRequest(RequestModel):
    stock_material_id: int
    version: int | None = None


class BusinessEventRead(ReadModel):
    id: int
    action: str
    old_status: str | None = None
    new_status: str | None = None
    operator_name: str
    occurred_at: datetime
    remark: str | None = None


class ActionVersion(RequestModel):
    version: int | None = None


class ReasonAction(ActionVersion):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class PurchaseRequestLineWrite(RequestModel):
    id: int | None = None
    purchase_material_id: int
    requested_qty: PositiveQuantity
    usage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None


class PurchaseRequestCreate(RequestModel):
    request_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    remark: str | None = Field(default=None, max_length=1000)
    lines: list[PurchaseRequestLineWrite] = Field(default_factory=list)


class PurchaseRequestUpdate(PurchaseRequestCreate):
    version: int


class PurchaseRequestLineRead(ReadModel):
    id: int
    purchase_material_id: int
    material_code_snapshot: str | None = None
    material_name_snapshot: str
    model_spec_snapshot: str
    unit_name_snapshot: str
    requested_qty: Decimal
    received_qty: Decimal
    usage: str
    subitem_no: str | None = None


class PurchaseRequestRead(ReadModel):
    id: int
    request_no: str
    status: PurchaseRequestStatus
    applicant_name: str
    handler_name: str | None = None
    salesperson: str | None = None
    remark: str | None = None
    return_reason: str | None = None
    close_reason: str | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    version: int
    lines: list[PurchaseRequestLineRead]
    events: list[BusinessEventRead]


class MovePurchasePlanRequest(RequestModel):
    request_no: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    remark: str | None = Field(default=None, max_length=1000)


class PurchaseRecordUpdate(RequestModel):
    request_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    remark: str | None = Field(default=None, max_length=1000)
    version: int


class PurchaseRecordRead(ReadModel):
    line_id: int
    purchase_request_id: int
    purchase_material_id: int
    request_no: str
    status: PurchaseRequestStatus
    material_code: str
    material_name: str
    model_spec: str
    unit_name: str
    planned_qty: Decimal
    received_qty: Decimal
    remaining_qty: Decimal
    actual_demand_person: str
    purchase_responsible: str
    salesperson: str | None = None
    remark: str | None = None
    usage: str
    subitem_no: str | None = None
    stock_material_id: int | None = None
    submitted_at: datetime | None = None
    created_at: datetime
    version: int


class PreparedInboundRead(ReadModel):
    purchase_request_no: str
    line_id: int
    purchase_material_id: int
    material_name: str
    model_spec: str
    unit_name: str
    remaining_qty: Decimal
    stock_material_id: int | None = None


class ReplenishmentDraftRead(ReadModel):
    next: Literal["purchase_material"]
    resource_id: int


class DashboardSummaryRead(ReadModel):
    stock_material_count: int
    low_stock_count: int
    pending_purchase_count: int
    on_order_count: int
    uncoded_purchase_material_count: int
    pending_purchase_request_count: int
    partially_received_count: int


__all__ = [name for name in globals() if not name.startswith("_")]
