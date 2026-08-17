from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, TINYINT
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base
from app.domain.enums import (
    ExcelExportJobStatus,
    ExcelImportJobStatus,
    OperationType,
    PurchasePlanStatus,
    Role,
    SourceType,
    WebhookDeliveryStatus,
    WebhookEventType,
    WebhookPlatform,
)

BIGINT_ID = BIGINT(unsigned=True).with_variant(Integer, "sqlite")
UINT = MYSQL_INTEGER(unsigned=True).with_variant(Integer, "sqlite")
UTINYINT = TINYINT(unsigned=True).with_variant(SmallInteger, "sqlite")
UTC_DATETIME = DATETIME(fsp=6).with_variant(DateTime(timezone=False), "sqlite")
QTY = Numeric(18, 1)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_api_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1")


class User(Base):
    __tablename__ = "user"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 接口令牌只存 SHA-256 哈希，明文仅在建/重新生成时返回一次（见 dictionary_service）。
    api_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: _hash_api_token(str(uuid4()))
    )
    # 非持久化字段：仅承载最近一次生成/重新生成的明文令牌，用于一次性返回。
    api_token: str | None = None
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1")


class MiniProgramUser(AuditMixin, Base):
    __tablename__ = "mini_program_user"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="华星检修维护部电气车间",
        server_default="华星检修维护部电气车间",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    identities: Mapped[list[MiniProgramIdentity]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="MiniProgramIdentity.app_id",
    )


class MiniProgramIdentity(AuditMixin, Base):
    __tablename__ = "mini_program_identity"
    __table_args__ = (
        UniqueConstraint("app_id", "wechat_openid"),
        UniqueConstraint("mini_program_user_id", "app_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    mini_program_user_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey("mini_program_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    wechat_openid: Mapped[str] = mapped_column(String(128), nullable=False)
    user: Mapped[MiniProgramUser] = relationship(back_populates="identities")


class MaterialCodeLibrary(Base):
    __tablename__ = "material_code_library"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    model_spec: Mapped[str | None] = mapped_column(String(255))
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )


class ExcelImportJob(Base):
    __tablename__ = "excel_import_job"
    __table_args__ = (Index("ix_excel_import_job_type_status", "import_type", "status", "id"),)

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    import_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ExcelImportJobStatus] = mapped_column(
        SAEnum(ExcelImportJobStatus),
        nullable=False,
        default=ExcelImportJobStatus.PENDING,
        server_default=ExcelImportJobStatus.PENDING.value,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    finished_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )


class HuaXingInventory(Base):
    __tablename__ = "huaxing_inventory"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    first_inbound_date: Mapped[date | None] = mapped_column(Date)
    warehouse: Mapped[str | None] = mapped_column(String(128))
    material_code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    model_spec: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    unit_name: Mapped[str | None] = mapped_column(String(32))
    purchaser: Mapped[str | None] = mapped_column(String(128))
    purchase_department: Mapped[str | None] = mapped_column(String(128))
    subitem_no_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )


class ExcelExportJob(Base):
    """异步 Excel 导出任务（申购记录 / 申购计划结果导出共用）。

    与 excel_import_job 对称：PENDING → RUNNING → SUCCEEDED | FAILED。
    区别在于文件方向相反——file_path 指向后台生成的待下载文件（成功保留至保留期，
    失败/过期由 excel_export_job_service 清理），download_filename 为下载文件名。
    """

    __tablename__ = "excel_export_job"
    __table_args__ = (
        Index("ix_excel_export_job_type_status", "export_type", "status", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ExcelExportJobStatus] = mapped_column(
        SAEnum(ExcelExportJobStatus),
        nullable=False,
        default=ExcelExportJobStatus.PENDING,
        server_default=ExcelExportJobStatus.PENDING.value,
    )
    download_filename: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    # 导出请求参数快照（筛选条件/列），用于排查与潜在的重跑。
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    finished_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )


class FileObject(AuditMixin, Base):
    __tablename__ = "file_object"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image/png")
    size_bytes: Mapped[int] = mapped_column(BIGINT_ID, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class StockMaterial(AuditMixin, Base):
    __tablename__ = "stock_material"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_id: Mapped[str | None] = mapped_column(String(128))
    alias: Mapped[str | None] = mapped_column(String(128))
    model_spec: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(1000))
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    balance: Mapped[StockBalance | None] = relationship(
        back_populates="material", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    replenishment_policy: Mapped[StockReplenishmentPolicy | None] = relationship(
        back_populates="material", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    images: Mapped[list[StockMaterialImage]] = relationship(
        back_populates="material",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="StockMaterialImage.sort_order",
    )


class StockMaterialImage(Base):
    __tablename__ = "stock_material_image"

    material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("file_object.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0)
    material: Mapped[StockMaterial] = relationship(back_populates="images")
    file: Mapped[FileObject] = relationship(lazy="selectin")


class StockReplenishmentPolicy(Base):
    __tablename__ = "stock_replenishment_policy"
    __table_args__ = (CheckConstraint("minimum_qty >= 0", name="minimum_nonnegative"),)

    stock_material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id", ondelete="CASCADE"), primary_key=True
    )
    minimum_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1")
    material: Mapped[StockMaterial] = relationship(back_populates="replenishment_policy")


class StockBalance(Base):
    __tablename__ = "stock_balance"

    stock_material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"), server_default="0")
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    material: Mapped[StockMaterial] = relationship(back_populates="balance")


class PurchaseMaterial(AuditMixin, Base):
    __tablename__ = "purchase_material"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    plan_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    material_code: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    urgency: Mapped[str] = mapped_column(
        String(32), nullable=False, default="正常", server_default="正常"
    )
    demand_department: Mapped[str] = mapped_column(
        String(128), nullable=False, default="HXNI 检修维护部", server_default="HXNI 检修维护部"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_spec: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False)
    actual_demand_person: Mapped[str] = mapped_column(String(128), nullable=False)
    purchase_responsible: Mapped[str] = mapped_column(String(128), nullable=False)
    planned_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    usage: Mapped[str] = mapped_column(String(500), nullable=False)
    subitem_no: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(String(1000))
    stock_material_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id"), index=True
    )
    status: Mapped[PurchasePlanStatus] = mapped_column(
        SAEnum(PurchasePlanStatus),
        nullable=False,
        default=PurchasePlanStatus.NORMAL,
        server_default=PurchasePlanStatus.NORMAL.name,
        index=True,
    )
    stock_material: Mapped[StockMaterial | None] = relationship(lazy="selectin")
    images: Mapped[list[PurchaseMaterialImage]] = relationship(
        back_populates="material",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PurchaseMaterialImage.sort_order",
    )


class PurchaseMaterialImage(Base):
    __tablename__ = "purchase_material_image"

    material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_material.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("file_object.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0)
    material: Mapped[PurchaseMaterial] = relationship(back_populates="images")
    file: Mapped[FileObject] = relationship(lazy="selectin")


class PurchaseRequest(AuditMixin, Base):
    __tablename__ = "purchase_request"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    purchase_order_no: Mapped[str | None] = mapped_column(String(128))
    contract_no: Mapped[str | None] = mapped_column(String(128))
    vessel_no: Mapped[str | None] = mapped_column(String(128))
    consolidation_date: Mapped[date | None] = mapped_column(Date)
    consolidation_port: Mapped[str | None] = mapped_column(String(128))
    sailing_date: Mapped[date | None] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(String(1000))
    purchase_date: Mapped[date | None] = mapped_column(Date)

    lines: Mapped[list[PurchaseRequestLine]] = relationship(
        back_populates="request",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PurchaseRequestLine.id",
    )


class PurchaseRequestLine(AuditMixin, Base):
    __tablename__ = "purchase_request_line"
    __table_args__ = (
        CheckConstraint("purchase_qty > 0", name="purchase_positive"),
        # usage 最长 500 字符，直接进唯一索引浪费空间；改用 usage_hash 保持等值语义。
        UniqueConstraint(
            "purchase_request_id", "purchase_material_id", "subitem_no", "usage_hash"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    purchase_request_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_request.id", ondelete="CASCADE"), nullable=False
    )
    purchase_material_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_material.id", ondelete="SET NULL")
    )
    # 记录自包含快照：转入时从计划复制，读路径不再依赖 purchase_material（清理计划后仍可读）
    plan_no_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    material_code_snapshot: Mapped[str | None] = mapped_column(String(64))
    category_snapshot: Mapped[str | None] = mapped_column(String(64))
    demand_department_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    model_spec_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    actual_demand_person_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    purchase_responsible_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_remark_snapshot: Mapped[str | None] = mapped_column(String(1000))
    stock_material_id_snapshot: Mapped[int | None] = mapped_column(BIGINT_ID)
    purchase_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    status: Mapped[str] = mapped_column(String(128), nullable=False, default="已申购")
    usage: Mapped[str] = mapped_column(String(500), nullable=False)
    # usage 的归一化哈希（SHA-256 十六进制前 32 位），进唯一索引以替代 500 字符的 usage。
    usage_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    subitem_no: Mapped[str | None] = mapped_column(String(64))
    trace_no: Mapped[str | None] = mapped_column(String(128), index=True)
    salesperson: Mapped[str | None] = mapped_column(String(128))

    @validates("usage")
    def _sync_usage_hash(self, _key: str, value: str) -> str:
        usage = value if isinstance(value, str) else (value or "")
        self.usage_hash = hashlib.sha256(usage.encode("utf-8")).hexdigest()[:32]
        return value

    request: Mapped[PurchaseRequest] = relationship(back_populates="lines", lazy="selectin")
    purchase_material: Mapped[PurchaseMaterial | None] = relationship(lazy="selectin")
    images: Mapped[list[PurchaseRequestLineImage]] = relationship(
        back_populates="line",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PurchaseRequestLineImage.sort_order",
    )


class PurchaseRequestLineImage(Base):
    __tablename__ = "purchase_request_line_image"

    line_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_request_line.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("file_object.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0)
    line: Mapped[PurchaseRequestLine] = relationship(back_populates="images")
    file: Mapped[FileObject] = relationship(lazy="selectin")


class StockOperation(AuditMixin, Base):
    __tablename__ = "stock_operation"
    __table_args__ = (
        Index("ix_stock_operation_type_occurred", "operation_type", "occurred_at"),
        Index("ix_stock_operation_source_occurred", "source_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    operation_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    operation_type: Mapped[OperationType] = mapped_column(SAEnum(OperationType), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False, index=True)
    business_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    receiver_unit: Mapped[str | None] = mapped_column(String(128))
    receiver_name: Mapped[str | None] = mapped_column(String(64))
    subitem_no: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("stock_operation.id"), index=True
    )
    client_request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mini_program_user_name_snapshot: Mapped[str | None] = mapped_column(String(128))

    lines: Mapped[list[StockOperationLine]] = relationship(
        back_populates="operation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="StockOperationLine.id",
    )


class StockOperationLine(AuditMixin, Base):
    __tablename__ = "stock_operation_line"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="operation_quantity_positive"),
        UniqueConstraint("operation_id", "stock_material_id"),
        Index("ix_operation_line_material_operation", "stock_material_id", "operation_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    operation_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_operation.id", ondelete="CASCADE"), nullable=False
    )
    stock_material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    remaining_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    before_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    after_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    model_spec_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)

    operation: Mapped[StockOperation] = relationship(back_populates="lines")
    stock_material: Mapped[StockMaterial] = relationship(lazy="selectin")


class BusinessEventLog(Base):
    __tablename__ = "business_event_log"
    __table_args__ = (Index("ix_business_event_entity", "business_type", "business_id", "id"),)

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    business_id: Mapped[int] = mapped_column(BIGINT_ID, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    remark: Mapped[str | None] = mapped_column(String(1000))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class SystemSetting(Base):
    """系统设置键值表：替代把配置塞进 business_event_log 的做法。"""

    __tablename__ = "system_setting"

    setting_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    setting_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )


class WebhookChannel(AuditMixin, Base):
    __tablename__ = "webhook_channel"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    platform: Mapped[WebhookPlatform] = mapped_column(
        SAEnum(WebhookPlatform), unique=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    webhook_url_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    secret_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    subscribed_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"
    __table_args__ = (
        UniqueConstraint("event_id", "channel_id"),
        Index("ix_webhook_delivery_pending", "status", "next_retry_at", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[WebhookEventType] = mapped_column(SAEnum(WebhookEventType), nullable=False)
    channel_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("webhook_channel.id"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SAEnum(WebhookDeliveryStatus),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
        server_default=WebhookDeliveryStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0, server_default="0")
    next_retry_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_excerpt: Mapped[str | None] = mapped_column(String(1000))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)

    channel: Mapped[WebhookChannel] = relationship(lazy="joined")


__all__ = [
    "Base",
    "BusinessEventLog",
    "ExcelExportJob",
    "ExcelImportJob",
    "FileObject",
    "HuaXingInventory",
    "MiniProgramUser",
    "PurchaseMaterial",
    "PurchaseMaterialImage",
    "PurchaseRequest",
    "PurchaseRequestLine",
    "PurchaseRequestLineImage",
    "StockBalance",
    "StockMaterial",
    "StockMaterialImage",
    "StockOperation",
    "StockOperationLine",
    "StockReplenishmentPolicy",
    "User",
    "WebhookChannel",
    "WebhookDelivery",
]
