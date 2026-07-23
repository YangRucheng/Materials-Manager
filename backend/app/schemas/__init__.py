from __future__ import annotations

from datetime import date, datetime
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
    PurchasePlanStatus,
    Role,
    SourceType,
)

PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=1)]
NonnegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=1)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
FileId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
]


def _ensure_unique_image_ids(value: list[str]) -> list[str]:
    if len(value) != len(set(value)):
        raise ValueError("image_ids contains duplicates")
    return value


def _empty_string_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


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


class PurchaseFilterOptions(ReadModel):
    actual_demand_persons: list[str]
    purchase_responsibles: list[str]


class PurchaseRecordFilterOptions(PurchaseFilterOptions):
    salespersons: list[str]
    statuses: list[str]


class ApiError(ReadModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str


class AgentDatabaseExecuteRequest(RequestModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    sql: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)]
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    max_rows: int = Field(default=1000, ge=1, le=5000)


class AgentDatabaseExecuteRead(ReadModel):
    statement_type: Literal["SELECT", "INSERT", "UPDATE", "DELETE"]
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, object]] = Field(default_factory=list)
    row_count: int
    affected_rows: int | None = None
    last_insert_id: str | int | None = None
    truncated: bool = False


class AgentDatabaseSchemaRead(ReadModel):
    tables: list[dict[str, object]]


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
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)] | None
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
    id: FileId
    original_name: str
    mime_type: Literal["image/png"] = "image/png"
    size_bytes: int
    width: int
    height: int


class OrphanFileRead(ReadModel):
    id: FileId
    original_name: str
    size_bytes: int
    created_at: datetime
    file_exists: bool


class OrphanFileReportRead(ReadModel):
    cutoff: datetime
    unreferenced_records: list[OrphanFileRead]
    untracked_file_names: list[str]
    missing_file_ids: list[FileId]


class OrphanFileCleanupRead(ReadModel):
    cutoff: datetime
    deleted_record_ids: list[FileId]
    deleted_file_names: list[str]


class ReplenishmentPolicyRead(ReadModel):
    minimum_qty: Decimal
    enabled: bool
    version: int = 1


class ReplenishmentPolicyWrite(RequestModel):
    minimum_qty: NonnegativeQuantity
    enabled: bool = True
    version: int | None = None


class StockMaterialBase(RequestModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_id: int
    remark: str | None = Field(default=None, max_length=1000)
    image_ids: list[FileId] = Field(default_factory=list, max_length=9)

    @field_validator("image_ids")
    @classmethod
    def unique_images(cls, value: list[str]) -> list[str]:
        return _ensure_unique_image_ids(value)


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
    is_low_stock: bool
    suggested_purchase_qty: Decimal
    updated_at: datetime


class OperationLineWrite(RequestModel):
    stock_material_id: int
    quantity: PositiveQuantity


def _require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("occurred_at must include a timezone")
    return value


def _ensure_unique_operation_materials(
    value: list[OperationLineWrite],
) -> list[OperationLineWrite]:
    ids = [line.stock_material_id for line in value]
    if len(ids) != len(set(ids)):
        raise ValueError("one operation may only contain a material once")
    return value


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
        return _require_aware_datetime(value)

    @field_validator("lines")
    @classmethod
    def unique_materials(cls, value: list[OperationLineWrite]) -> list[OperationLineWrite]:
        return _ensure_unique_operation_materials(value)


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

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value)

    @field_validator("lines")
    @classmethod
    def unique_materials(cls, value: list[OperationLineWrite]) -> list[OperationLineWrite]:
        return _ensure_unique_operation_materials(value)


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


class StockOperationRead(ReadModel):
    id: int
    operation_no: str
    operation_type: OperationType
    occurred_at: datetime
    business_reason: str
    receiver_name: str | None = None
    subitem_no: str | None = None
    source_type: SourceType
    reversal_of_id: int | None = None
    client_request_id: str
    lines: list[StockOperationLineRead]
    created_at: datetime
    version: int


class PurchaseMaterialBase(RequestModel):
    plan_date: date | None = None
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
    image_ids: list[FileId] = Field(default_factory=list, max_length=9)
    status: PurchasePlanStatus = PurchasePlanStatus.NORMAL

    @field_validator("image_ids")
    @classmethod
    def unique_images(cls, value: list[str]) -> list[str]:
        return _ensure_unique_image_ids(value)

    @field_validator("material_code", mode="before")
    @classmethod
    def empty_code_to_none(cls, value: object) -> object:
        return _empty_string_to_none(value)


class PurchaseMaterialCreate(PurchaseMaterialBase):
    pass


class PurchaseMaterialUpdate(PurchaseMaterialBase):
    version: int


class PurchasePlanVersion(RequestModel):
    id: int
    version: int


class BatchUpdatePurchasePlansRequest(RequestModel):
    materials: list[PurchasePlanVersion] = Field(min_length=1, max_length=200)
    plan_date: date | None = None
    actual_demand_person: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    usage: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None
    status: PurchasePlanStatus | None = None

    @field_validator("materials")
    @classmethod
    def unique_materials(cls, value: list[PurchasePlanVersion]) -> list[PurchasePlanVersion]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("materials must be unique")
        return value

    @model_validator(mode="after")
    def validate_updates(self) -> BatchUpdatePurchasePlansRequest:
        update_fields = {"plan_date", "actual_demand_person", "subitem_no", "usage", "status"}
        selected_fields = self.model_fields_set & update_fields
        if not selected_fields:
            raise ValueError("at least one update field is required")
        for field in selected_fields - {"subitem_no"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PurchaseMaterialRead(ReadModel):
    id: int
    plan_no: str
    plan_date: date
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
    status: PurchasePlanStatus
    moved_to_record: bool
    enabled: bool
    images: list[FileObjectRead]
    created_at: datetime
    updated_at: datetime
    version: int


class LinkStockMaterialRequest(RequestModel):
    stock_material_id: int
    version: int | None = None


class ActionVersion(RequestModel):
    version: int | None = None


class MovePurchasePlanRequest(RequestModel):
    purchase_order_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    trace_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = None
    purchase_date: date
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    status: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ] = "已申购"
    record_remark: str | None = Field(default=None, max_length=1000)


class BatchMovePurchasePlansRequest(MovePurchasePlanRequest):
    material_ids: list[int] = Field(min_length=1, max_length=200)

    @field_validator("material_ids")
    @classmethod
    def unique_material_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("material_ids must be unique")
        return value


class PurchasePlanExportRequest(RequestModel):
    material_ids: list[int] = Field(min_length=1, max_length=200)

    @field_validator("material_ids")
    @classmethod
    def unique_material_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("material_ids must be unique")
        return value


class PurchaseRecordUpdate(RequestModel):
    plan_date: date
    material_code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    material_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_id: int
    actual_demand_person: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    purchase_responsible: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    purchase_qty: PositiveQuantity
    usage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    subitem_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    plan_remark: str | None = Field(default=None, max_length=1000)
    stock_material_id: int | None = None
    image_ids: list[FileId] = Field(default_factory=list, max_length=9)
    purchase_order_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    trace_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = None
    purchase_date: date | None = None
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    record_remark: str | None = Field(default=None, max_length=1000)
    version: int

    @field_validator("image_ids")
    @classmethod
    def unique_images(cls, value: list[str]) -> list[str]:
        return _ensure_unique_image_ids(value)

    @field_validator("material_code", mode="before")
    @classmethod
    def empty_code_to_none(cls, value: object) -> object:
        return _empty_string_to_none(value)


class PurchaseRecordRead(ReadModel):
    line_id: int
    purchase_request_id: int
    purchase_material_id: int
    plan_no: str
    plan_date: date
    purchase_order_no: str | None = None
    trace_no: str | None = None
    status: str
    material_code: str | None = None
    material_name: str
    model_spec: str
    unit_id: int
    unit_name: str
    purchase_qty: Decimal
    actual_demand_person: str
    purchase_responsible: str
    salesperson: str | None = None
    plan_remark: str | None = None
    record_remark: str | None = None
    usage: str
    subitem_no: str | None = None
    images: list[FileObjectRead]
    stock_material_id: int | None = None
    purchase_date: date | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class ReplenishmentDraftCreate(RequestModel):
    planned_qty: PositiveQuantity
    demand_date: date | None = None
    actual_demand_person: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    purchase_responsible: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]


class ReplenishmentDefaultsRead(ReadModel):
    purchase_responsible: str
    demand_date: date


class ReplenishmentDraftRead(ReadModel):
    next: Literal["purchase_material"]
    resource_id: int


class DashboardSummaryRead(ReadModel):
    stock_material_count: int
    low_stock_count: int
    uncoded_purchase_material_count: int
    purchase_record_count: int


__all__ = [name for name in globals() if not name.startswith("_")]
