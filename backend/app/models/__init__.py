from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import (
    OperationType,
    PurchaseRequestStatus,
    Role,
    SourceType,
)

BIGINT_ID = BIGINT(unsigned=True).with_variant(Integer, "sqlite")
UINT = MYSQL_INTEGER(unsigned=True).with_variant(Integer, "sqlite")
UTINYINT = TINYINT(unsigned=True).with_variant(SmallInteger, "sqlite")
UTC_DATETIME = DATETIME(fsp=6).with_variant(DateTime(timezone=False), "sqlite")
QTY = Numeric(18, 1)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    created_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"), nullable=True)
    version: Mapped[int] = mapped_column(UINT, default=1, server_default="1")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
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


class MeasurementUnit(AuditMixin, Base):
    __tablename__ = "measurement_unit"
    __table_args__ = (
        CheckConstraint("decimal_places >= 0 AND decimal_places <= 1", name="decimal_places_range"),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    decimal_places: Mapped[int] = mapped_column(UTINYINT, default=0, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class ProjectSubitem(AuditMixin, Base):
    __tablename__ = "project_subitem"
    __table_args__ = (UniqueConstraint("project_code", "subitem_no"),)

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(64), nullable=False)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    subitem_no: Mapped[str] = mapped_column(String(64), nullable=False)
    subitem_name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class FileObject(AuditMixin, Base):
    __tablename__ = "file_object"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image/png")
    size_bytes: Mapped[int] = mapped_column(BIGINT_ID, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class StockMaterial(AuditMixin, Base):
    __tablename__ = "stock_material"

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_spec: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("measurement_unit.id"), nullable=False
    )
    remark: Mapped[str | None] = mapped_column(String(1000))
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    unit: Mapped[MeasurementUnit] = relationship(lazy="selectin")
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
    file_id: Mapped[int] = mapped_column(BIGINT_ID, ForeignKey("file_object.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0)
    material: Mapped[StockMaterial] = relationship(back_populates="images")
    file: Mapped[FileObject] = relationship(lazy="selectin")


class StockReplenishmentPolicy(Base):
    __tablename__ = "stock_replenishment_policy"
    __table_args__ = (
        CheckConstraint("minimum_qty >= 0", name="minimum_nonnegative"),
        CheckConstraint("target_qty >= minimum_qty", name="target_at_least_minimum"),
    )

    stock_material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id", ondelete="CASCADE"), primary_key=True
    )
    minimum_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    target_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), onupdate=_utcnow
    )
    created_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"))
    updated_by: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"))
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
    material_code: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_spec: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("measurement_unit.id"), nullable=False
    )
    actual_demand_person: Mapped[str] = mapped_column(String(128), nullable=False)
    purchase_responsible: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    planned_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    usage: Mapped[str] = mapped_column(String(500), nullable=False)
    project_subitem_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("project_subitem.id"), index=True
    )
    remark: Mapped[str | None] = mapped_column(String(1000))
    stock_material_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("stock_material.id"), index=True
    )
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    unit: Mapped[MeasurementUnit] = relationship(lazy="selectin")
    project_subitem: Mapped[ProjectSubitem | None] = relationship(lazy="selectin")
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
    file_id: Mapped[int] = mapped_column(BIGINT_ID, ForeignKey("file_object.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(UTINYINT, nullable=False, default=0)
    material: Mapped[PurchaseMaterial] = relationship(back_populates="images")
    file: Mapped[FileObject] = relationship(lazy="selectin")


class PurchaseRequest(AuditMixin, Base):
    __tablename__ = "purchase_request"
    __table_args__ = (Index("ix_purchase_request_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[PurchaseRequestStatus] = mapped_column(
        SAEnum(PurchaseRequestStatus), nullable=False
    )
    applicant_id: Mapped[int] = mapped_column(BIGINT_ID, ForeignKey("user.id"), nullable=False)
    handler_id: Mapped[int | None] = mapped_column(BIGINT_ID, ForeignKey("user.id"))
    salesperson: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(String(1000))
    return_reason: Mapped[str | None] = mapped_column(String(500))
    close_reason: Mapped[str | None] = mapped_column(String(500))
    submitted_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    completed_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)

    applicant: Mapped[User] = relationship(foreign_keys=[applicant_id], lazy="selectin")
    handler: Mapped[User | None] = relationship(foreign_keys=[handler_id], lazy="selectin")
    lines: Mapped[list[PurchaseRequestLine]] = relationship(
        back_populates="request",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PurchaseRequestLine.id",
    )


class PurchaseRequestLine(AuditMixin, Base):
    __tablename__ = "purchase_request_line"
    __table_args__ = (
        CheckConstraint("requested_qty > 0", name="requested_positive"),
        CheckConstraint("received_qty >= 0", name="received_nonnegative"),
        UniqueConstraint(
            "purchase_request_id", "purchase_material_id", "project_subitem_id", "usage"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    purchase_request_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_request.id", ondelete="CASCADE"), nullable=False
    )
    purchase_material_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_material.id"), nullable=False
    )
    material_code_snapshot: Mapped[str | None] = mapped_column(String(64))
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    model_spec_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"), server_default="0")
    usage: Mapped[str] = mapped_column(String(500), nullable=False)
    project_subitem_id: Mapped[int] = mapped_column(
        BIGINT_ID, ForeignKey("project_subitem.id"), nullable=False
    )
    project_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    subitem_no_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    subitem_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)

    request: Mapped[PurchaseRequest] = relationship(back_populates="lines", lazy="selectin")
    purchase_material: Mapped[PurchaseMaterial] = relationship(lazy="selectin")
    project_subitem: Mapped[ProjectSubitem] = relationship(lazy="selectin")


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
    operator_id: Mapped[int] = mapped_column(BIGINT_ID, ForeignKey("user.id"), nullable=False)
    business_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    receiver_name: Mapped[str | None] = mapped_column(String(64))
    project_subitem_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("project_subitem.id")
    )
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("stock_operation.id"), unique=True
    )
    client_request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    operator: Mapped[User] = relationship(foreign_keys=[operator_id], lazy="selectin")
    project_subitem: Mapped[ProjectSubitem | None] = relationship(lazy="selectin")
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
    before_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    after_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    model_spec_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_name_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_request_line_id: Mapped[int | None] = mapped_column(
        BIGINT_ID, ForeignKey("purchase_request_line.id")
    )

    operation: Mapped[StockOperation] = relationship(back_populates="lines")
    stock_material: Mapped[StockMaterial] = relationship(lazy="selectin")
    purchase_request_line: Mapped[PurchaseRequestLine | None] = relationship(lazy="selectin")


class BusinessEventLog(Base):
    __tablename__ = "business_event_log"
    __table_args__ = (Index("ix_business_event_entity", "business_type", "business_id", "id"),)

    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False)
    business_id: Mapped[int] = mapped_column(BIGINT_ID, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    operator_id: Mapped[int] = mapped_column(BIGINT_ID, ForeignKey("user.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=_utcnow, server_default=func.now(), nullable=False
    )
    remark: Mapped[str | None] = mapped_column(String(1000))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    operator: Mapped[User] = relationship(lazy="selectin")


__all__ = [
    "Base",
    "BusinessEventLog",
    "FileObject",
    "MeasurementUnit",
    "ProjectSubitem",
    "PurchaseMaterial",
    "PurchaseMaterialImage",
    "PurchaseRequest",
    "PurchaseRequestLine",
    "StockBalance",
    "StockMaterial",
    "StockMaterialImage",
    "StockOperation",
    "StockOperationLine",
    "StockReplenishmentPolicy",
    "User",
]
