from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    WAREHOUSE_ADMIN = "WAREHOUSE_ADMIN"
    PURCHASE_ADMIN = "PURCHASE_ADMIN"
    READ_ONLY = "READ_ONLY"


class OperationType(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class SourceType(StrEnum):
    MANUAL = "MANUAL"
    REVERSAL = "REVERSAL"
    INITIALIZATION = "INITIALIZATION"


class PurchasePlanStatus(StrEnum):
    NORMAL = "正常"
    DEFERRED = "暂不申购"
    ARCHIVED = "已归档"
