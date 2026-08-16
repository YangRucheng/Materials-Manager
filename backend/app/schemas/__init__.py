from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from app.domain.enums import (
    ExcelImportJobStatus,
    MiniProgramCodeEnv,
    MiniProgramFeatureMode,
    MiniProgramStockStatus,
    OperationType,
    PurchasePlanStatus,
    Role,
    SourceType,
    WebhookEventType,
    WebhookPlatform,
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
ApiToken = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
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


def _to_utc_iso(value: datetime) -> str:
    """naive 值按 UTC 处理（存储层 utcnow() 即 naive UTC），aware 值转为 UTC。

    约定：服务端一律输出带 +00:00 的 ISO 字符串，客户端按上海时区展示。
    """
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat()


# 用于需要统一输出 UTC 时区的 datetime 字段（尤其是经 model_validate 直接序列化的读模型）。
# WithJsonSchema 显式声明 JSON Schema，避免 PlainSerializer 使 openapi 丢失 format: date-time。
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(_to_utc_iso, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]


class Page[T](ReadModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class PurchaseFilterOptions(ReadModel):
    actual_demand_persons: list[str]
    purchase_responsibles: list[str]
    subitem_nos: list[str]
    categories: list[str]


class PurchaseRecordFilterOptions(PurchaseFilterOptions):
    salespersons: list[str]
    statuses: list[str]


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


class UserApiTokenRead(UserRead):
    # 令牌明文仅在新建/重新生成接口中返回一次；列表读取为 None（库中只存哈希）。
    api_token: ApiToken | None = None


class LoginRequest(RequestModel):
    username: NonBlank
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(ReadModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead


class RefreshTokenRequest(RequestModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenPairResponse(ReadModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


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


class UserApiTokenRegenerate(RequestModel):
    version: int


class MiniProgramIdentityRead(ReadModel):
    id: int
    app_id: str
    wechat_openid: str
    created_at: UtcDateTime


class MiniProgramUserRead(ReadModel):
    id: int
    display_name: str
    department_name: str
    enabled: bool
    identities: list[MiniProgramIdentityRead]
    created_at: UtcDateTime
    updated_at: UtcDateTime
    version: int


class MiniProgramUserUpdate(RequestModel):
    display_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
        | None
    ) = None
    department_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    enabled: bool | None = None
    version: int


class MiniProgramUserMergeRequest(RequestModel):
    source_user_id: int = Field(gt=0)
    source_version: int
    target_version: int


class MiniProgramLoginResponse(ReadModel):
    access_token: str | None = None
    registration_token: str | None = None
    token_type: Literal["bearer"] = "bearer"
    user: MiniProgramUserRead | None = None
    requires_profile: bool


class MiniProgramWechatLoginRequest(RequestModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    app_id: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
        | None
    ) = None


class MiniProgramProfileUpdate(RequestModel):
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    department_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]


class AiSearchSettingsRead(ReadModel):
    endpoint: str
    api_key: str
    model: str
    enabled: bool
    mini_program_code_env: MiniProgramCodeEnv
    mini_program_code_app_id: str
    mini_program_app_ids: list[str]
    mini_program_registration_enabled: bool
    mini_program_new_user_enabled: bool
    image_acceleration_server_url: str
    inventory_mode: MiniProgramFeatureMode
    huaxing_inventory_mode: MiniProgramFeatureMode
    purchase_plans_mode: MiniProgramFeatureMode
    purchase_records_mode: MiniProgramFeatureMode
    material_codes_mode: MiniProgramFeatureMode
    updated_at: datetime | None = None
    version: int


class AiSearchSettingsUpdate(RequestModel):
    endpoint: str = Field(default="", max_length=500)
    api_key: str = Field(default="", max_length=1000)
    model: str = Field(default="", max_length=128)
    enabled: bool = True
    mini_program_code_env: MiniProgramCodeEnv = MiniProgramCodeEnv.RELEASE
    mini_program_code_app_id: str = Field(default="", max_length=64)
    mini_program_registration_enabled: bool = True
    mini_program_new_user_enabled: bool = True
    image_acceleration_server_url: str = Field(default="", max_length=500)
    inventory_mode: MiniProgramFeatureMode = MiniProgramFeatureMode.READ_WRITE
    huaxing_inventory_mode: MiniProgramFeatureMode = MiniProgramFeatureMode.QUERY_ONLY
    purchase_plans_mode: MiniProgramFeatureMode = MiniProgramFeatureMode.QUERY_ONLY
    purchase_records_mode: MiniProgramFeatureMode = MiniProgramFeatureMode.QUERY_ONLY
    material_codes_mode: MiniProgramFeatureMode = MiniProgramFeatureMode.QUERY_ONLY
    version: int = Field(ge=0)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("端点必须使用 http:// 或 https://")
        return value

    @field_validator("image_acceleration_server_url")
    @classmethod
    def validate_image_acceleration_server_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("图片加速服务器必须使用 http:// 或 https://")
        return value

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        value = value.strip()
        return value

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, value: str) -> str:
        value = value.strip()
        return value

    @model_validator(mode="after")
    def require_enabled_model_config(self) -> AiSearchSettingsUpdate:
        if self.enabled and not (self.endpoint and self.api_key and self.model):
            raise ValueError("启用模型服务时必须填写端点、模型和 API Key")
        return self


class WebhookChannelRead(ReadModel):
    platform: WebhookPlatform
    enabled: bool
    subscribed_events: list[WebhookEventType]
    webhook_url: str
    secret: str
    webhook_configured: bool
    secret_configured: bool
    updated_at: datetime | None = None
    version: int


class WebhookChannelUpdate(RequestModel):
    enabled: bool = False
    webhook_url: str = Field(default="", max_length=2000)
    secret: str = Field(default="", max_length=1000)
    subscribed_events: list[WebhookEventType] = Field(default_factory=list, max_length=3)
    version: int = Field(ge=0)

    @field_validator("subscribed_events")
    @classmethod
    def unique_subscribed_events(cls, value: list[WebhookEventType]) -> list[WebhookEventType]:
        if len(value) != len(set(value)):
            raise ValueError("subscribed_events contains duplicates")
        return value


class WebhookTestRead(ReadModel):
    platform: WebhookPlatform
    success: bool
    message: str


class WebhookTestRequest(RequestModel):
    webhook_url: str = Field(max_length=2000)
    secret: str = Field(default="", max_length=1000)


class AiSearchStatusRead(BaseModel):
    available: bool


class ImageAccelerationSettingsRead(BaseModel):
    image_acceleration_server_url: str


class MiniProgramFeaturesRead(BaseModel):
    inventory_mode: MiniProgramFeatureMode
    huaxing_inventory_mode: MiniProgramFeatureMode
    purchase_plans_mode: MiniProgramFeatureMode
    purchase_records_mode: MiniProgramFeatureMode
    material_codes_mode: MiniProgramFeatureMode


class AiSearchExpandRequest(RequestModel):
    value: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class AiSearchExpandRead(BaseModel):
    original: str
    expanded: str


class AiSearchTestRead(BaseModel):
    original: str
    expanded: str


class AiSearchTestRequest(RequestModel):
    endpoint: str = Field(max_length=500)
    api_key: str = Field(max_length=1000)
    model: str = Field(max_length=128)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("端点必须使用 http:// 或 https://")
        return value

    @field_validator("api_key", "model")
    @classmethod
    def require_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


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
    name_id: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=128)
    ] = None
    alias: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=128)
    ] = None
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ]
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
    uuid: UUID
    name: str
    name_id: str | None = None
    alias: str | None = None
    model_spec: str
    unit_name: str
    remark: str | None = None
    current_qty: Decimal
    images: list[FileObjectRead]
    replenishment_policy: ReplenishmentPolicyRead | None = None
    has_operation_records: bool = False
    created_at: datetime
    updated_at: datetime
    version: int


class InventoryBalanceRead(ReadModel):
    stock_material_id: int
    name: str
    alias: str | None = None
    model_spec: str
    unit_name: str
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
    receiver_unit: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
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
    receiver_unit: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
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
    lines: list[OperationLineWrite] = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def unique_materials(cls, value: list[OperationLineWrite]) -> list[OperationLineWrite]:
        return _ensure_unique_operation_materials(value)


class StockOperationLineRead(ReadModel):
    id: int
    stock_material_id: int
    material_name: str
    model_spec: str
    unit_name: str
    quantity: Decimal
    remaining_qty: Decimal
    before_qty: Decimal
    after_qty: Decimal


class StockOperationRead(ReadModel):
    id: int
    operation_no: str
    operation_type: OperationType
    occurred_at: datetime
    business_reason: str
    receiver_unit: str | None = None
    receiver_name: str | None = None
    subitem_no: str | None = None
    source_type: SourceType
    reversal_of_id: int | None = None
    is_reversed: bool = False
    client_request_id: str
    mini_program_user_name: str | None = None
    lines: list[StockOperationLineRead]
    created_at: datetime
    version: int


class MiniProgramMaterialRead(ReadModel):
    uuid: UUID
    name: str
    model_spec: str
    unit_name: str
    current_qty: Decimal
    stock_status: MiniProgramStockStatus
    minimum_qty: Decimal | None = None
    remark: str | None = None
    images: list[FileObjectRead] = Field(default_factory=list)


class MiniProgramInventoryItemRead(ReadModel):
    uuid: UUID
    name: str
    model_spec: str
    unit_name: str
    current_qty: Decimal
    stock_status: MiniProgramStockStatus


class MiniProgramPurchasePlanItemRead(ReadModel):
    id: int
    plan_no: str
    plan_date: date
    name: str
    model_spec: str
    unit_name: str
    planned_qty: Decimal
    actual_demand_person: str
    purchase_responsible: str
    urgency: str


class MiniProgramPurchasePlanDetailRead(MiniProgramPurchasePlanItemRead):
    material_code: str | None = None
    category: str | None = None
    demand_department: str
    usage: str
    subitem_no: str | None = None
    remark: str | None = None
    images: list[FileObjectRead] = Field(default_factory=list)
    next_id: int | None = None


class MiniProgramPurchasePlanFilterOptions(ReadModel):
    actual_demand_persons: list[str]
    subitem_nos: list[str]


class MiniProgramPurchaseRecordItemRead(ReadModel):
    line_id: int
    material_name: str
    model_spec: str
    purchase_order_no: str | None = None
    trace_no: str | None = None
    status: str
    unit_name: str
    purchase_qty: Decimal
    plan_date: date
    subitem_no: str | None = None


class MiniProgramPurchaseRecordFilterOptions(ReadModel):
    statuses: list[str]
    subitem_nos: list[str]


class MiniProgramMaterialCodeRead(ReadModel):
    id: int
    material_code: str
    name: str | None = None
    model_spec: str | None = None
    unit_name: str


class MiniProgramHuaXingInventoryRead(ReadModel):
    id: int
    first_inbound_date: date | None = None
    warehouse: str | None = None
    material_code: str | None = None
    name: str | None = None
    model_spec: str | None = None
    quantity: Decimal | None = None
    unit_name: str | None = None
    purchaser: str | None = None
    purchase_department: str | None = None
    subitem_no_name: str | None = None


class MiniProgramOutboundCreate(RequestModel):
    client_request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    material_uuid: UUID
    occurred_at: datetime
    quantity: PositiveQuantity
    business_reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    receiver_unit: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=128)
    ] = ""
    subitem_no: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value)


class MiniProgramOutboundRead(ReadModel):
    operation_id: int
    operation_no: str
    material_uuid: UUID
    material_name: str
    model_spec: str
    unit_name: str
    quantity: Decimal
    before_qty: Decimal
    after_qty: Decimal
    occurred_at: datetime
    business_reason: str
    receiver_unit: str | None = None
    receiver_name: str
    subitem_no: str | None = None
    executed_by: str


class MiniProgramOutboundReason(ReadModel):
    subitem_no: str | None = None
    reason: str


class MiniProgramOutboundReasonOptions(ReadModel):
    personal_reasons: list[MiniProgramOutboundReason]
    system_reasons: list[MiniProgramOutboundReason]


class MiniProgramOperationRead(ReadModel):
    """小程序端出入库记录（按姓名匹配，行级展平）。

    兼容入库/出库、小程序/管理端来源；多行操作按行展平为多条记录。
    """

    operation_id: int
    operation_no: str
    operation_type: OperationType
    material_name: str
    model_spec: str
    unit_name: str
    quantity: Decimal
    before_qty: Decimal
    after_qty: Decimal
    occurred_at: datetime
    business_reason: str
    receiver_unit: str | None = None
    receiver_name: str | None = None
    subitem_no: str | None = None
    executed_by: str | None = None


class PurchaseMaterialBase(RequestModel):
    plan_date: date | None = None
    material_code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    urgency: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ] = "正常"
    demand_department: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ] = "HXNI 检修维护部"
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ]
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

    @field_validator("material_code", "category", mode="before")
    @classmethod
    def empty_optional_text_to_none(cls, value: object) -> object:
        return _empty_string_to_none(value)


class PurchaseMaterialCreate(PurchaseMaterialBase):
    pass


class PurchaseMaterialUpdate(PurchaseMaterialBase):
    version: int


class MaterialCodeLibraryRead(ReadModel):
    id: int
    material_code: str
    name: str | None
    model_spec: str | None
    unit_name: str


class MaterialCodeExistsRead(ReadModel):
    material_code: str
    exists: bool


class MaterialCodeLibraryImportRead(ReadModel):
    imported_count: int
    blank_name_count: int
    blank_model_spec_count: int


class ExcelImportJobRead(ReadModel):
    id: int
    import_type: str
    status: ExcelImportJobStatus
    original_filename: str
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: UtcDateTime
    started_at: UtcDateTime | None = None
    finished_at: UtcDateTime | None = None


class HuaXingInventoryRead(ReadModel):
    id: int
    first_inbound_date: date | None = None
    warehouse: str | None = None
    material_code: str | None = None
    name: str | None = None
    model_spec: str | None = None
    quantity: Decimal | None = None
    unit_name: str | None = None
    purchaser: str | None = None
    purchase_department: str | None = None
    subitem_no_name: str | None = None


class LastImportRead(ReadModel):
    last_import_at: UtcDateTime | None = None


class PurchasePlanVersion(RequestModel):
    id: int
    version: int


class BatchUpdatePurchasePlansRequest(RequestModel):
    materials: list[PurchasePlanVersion] = Field(min_length=1, max_length=200)
    plan_date: date | None = None
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    urgency: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)] | None
    ) = None
    demand_department: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    actual_demand_person: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    purchase_responsible: (
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
        update_fields = {
            "plan_date",
            "category",
            "urgency",
            "demand_department",
            "actual_demand_person",
            "purchase_responsible",
            "subitem_no",
            "usage",
            "status",
        }
        selected_fields = self.model_fields_set & update_fields
        if not selected_fields:
            raise ValueError("at least one update field is required")
        for field in selected_fields - {"category", "subitem_no"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PurchaseMaterialRead(ReadModel):
    id: int
    plan_no: str
    plan_date: date
    material_code: str | None = None
    category: str | None = None
    urgency: str
    demand_department: str
    name: str
    model_spec: str
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
    contract_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    vessel_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    consolidation_date: date | None = None
    consolidation_port: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    sailing_date: date | None = None
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


PurchasePlanResultColumn = Literal[
    "plan_no",
    "plan_date",
    "material_code",
    "category",
    "urgency",
    "demand_department",
    "name",
    "model_spec",
    "planned_qty",
    "unit_name",
    "actual_demand_person",
    "purchase_responsible",
    "subitem_no",
    "usage",
    "images",
]


class PurchasePlanResultExportRequest(RequestModel):
    columns: list[PurchasePlanResultColumn] = Field(min_length=1, max_length=15)
    name: str | None = Field(default=None, max_length=128)
    model_spec: str | None = Field(default=None, max_length=255)
    actual_demand_person: str | None = Field(default=None, max_length=128)
    empty_actual_demand_person: bool = False
    subitem_no: str | None = Field(default=None, max_length=64)
    empty_subitem_no: bool = False
    status: PurchasePlanStatus | list[PurchasePlanStatus] | None = None
    category: str | None = Field(default=None, max_length=64)
    sort_by: PurchasePlanResultColumn | None = None
    sort_order: Literal["asc", "desc"] = "asc"

    @field_validator("columns")
    @classmethod
    def unique_columns(
        cls, value: list[PurchasePlanResultColumn]
    ) -> list[PurchasePlanResultColumn]:
        if len(value) != len(set(value)):
            raise ValueError("columns must be unique")
        return value


class PurchaseRecordUpdate(RequestModel):
    plan_date: date
    material_code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    demand_department: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ] = "HXNI 检修维护部"
    material_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    model_spec: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    unit_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ]
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
    contract_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    vessel_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    consolidation_date: date | None = None
    consolidation_port: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    sailing_date: date | None = None
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

    @field_validator("material_code", "category", mode="before")
    @classmethod
    def empty_optional_text_to_none(cls, value: object) -> object:
        return _empty_string_to_none(value)


class PurchaseRecordVersion(RequestModel):
    line_id: int
    version: int


class BatchUpdatePurchaseRecordsRequest(RequestModel):
    records: list[PurchaseRecordVersion] = Field(min_length=1, max_length=200)
    plan_date: date | None = None
    purchase_order_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    trace_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = None
    contract_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    vessel_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = (
        None
    )
    consolidation_date: date | None = None
    consolidation_port: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    sailing_date: date | None = None
    purchase_date: date | None = None
    actual_demand_person: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    purchase_responsible: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    status: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
        | None
    ) = None
    record_remark: str | None = Field(default=None, max_length=1000)

    @field_validator("records")
    @classmethod
    def unique_records(cls, value: list[PurchaseRecordVersion]) -> list[PurchaseRecordVersion]:
        line_ids = [item.line_id for item in value]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("records must be unique")
        return value

    @model_validator(mode="after")
    def validate_updates(self) -> BatchUpdatePurchaseRecordsRequest:
        update_fields = {
            "plan_date",
            "purchase_order_no",
            "trace_no",
            "contract_no",
            "vessel_no",
            "consolidation_date",
            "consolidation_port",
            "sailing_date",
            "purchase_date",
            "actual_demand_person",
            "purchase_responsible",
            "salesperson",
            "status",
            "record_remark",
        }
        selected_fields = self.model_fields_set & update_fields
        if not selected_fields:
            raise ValueError("at least one update field is required")
        required_fields = {"plan_date", "actual_demand_person", "purchase_responsible", "status"}
        for field in selected_fields & required_fields:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PurchaseRecordRead(ReadModel):
    line_id: int
    purchase_request_id: int
    purchase_material_id: int | None
    plan_no: str
    plan_date: date
    purchase_order_no: str | None = None
    trace_no: str | None = None
    contract_no: str | None = None
    vessel_no: str | None = None
    consolidation_date: date | None = None
    consolidation_port: str | None = None
    sailing_date: date | None = None
    status: str
    material_code: str | None = None
    category: str | None = None
    demand_department: str
    material_name: str
    model_spec: str
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


PurchaseRecordResultColumn = Literal[
    "purchase_qty",
    "plan_date",
    "purchase_order_no",
    "trace_no",
    "contract_no",
    "vessel_no",
    "consolidation_date",
    "consolidation_port",
    "sailing_date",
    "category",
    "demand_department",
    "material_name",
    "model_spec",
    "material_code",
    "actual_demand_person",
    "usage",
    "purchase_responsible",
    "salesperson",
    "status",
    "purchase_date",
    "images",
    "subitem_no",
]


class PurchaseRecordResultExportRequest(RequestModel):
    columns: list[PurchaseRecordResultColumn] = Field(min_length=1, max_length=22)
    purchase_order_no: str | None = Field(default=None, max_length=255)
    trace_no: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=128)
    model_spec: str | None = Field(default=None, max_length=255)
    actual_demand_person: str | None = Field(default=None, max_length=128)
    purchase_responsible: str | None = Field(default=None, max_length=128)
    salesperson: str | None = Field(default=None, max_length=128)
    status: str | None = Field(default=None, max_length=128)
    empty_status: bool = False
    subitem_no: str | None = Field(default=None, max_length=64)
    empty_subitem_no: bool = False
    sort_by: PurchaseRecordResultColumn | None = None
    sort_order: Literal["asc", "desc"] = "asc"

    @field_validator("columns")
    @classmethod
    def unique_columns(
        cls, value: list[PurchaseRecordResultColumn]
    ) -> list[PurchaseRecordResultColumn]:
        if len(value) != len(set(value)):
            raise ValueError("columns must be unique")
        return value


class PurchaseRecordSyncTargetRead(ReadModel):
    trace_no: str
    target_count: int
    cursor_id: int


class PurchaseRecordSyncTargetsRead(ReadModel):
    items: list[PurchaseRecordSyncTargetRead]
    has_more: bool
    next_cursor: int = 0


class PurchaseRecordSyncTraceUpdate(RequestModel):
    salesperson: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    contract_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    vessel_no: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    consolidation_port: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None
    consolidation_date: date | None = None
    sailing_date: date | None = None
    status: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None
    ) = None


class PurchaseRecordSyncResultRead(ReadModel):
    affected_headers: int
    affected_lines: int


class VersionInfoRead(ReadModel):
    app_name: str
    version: str
    commit: str | None = None
    build_time: str | None = None


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
