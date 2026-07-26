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
    MINI_PROGRAM = "MINI_PROGRAM"
    REVERSAL = "REVERSAL"
    INITIALIZATION = "INITIALIZATION"


class MiniProgramCodeEnv(StrEnum):
    TRIAL = "trial"
    RELEASE = "release"


class MiniProgramStockStatus(StrEnum):
    NORMAL = "normal"
    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"


class PurchasePlanStatus(StrEnum):
    NORMAL = "正常"
    DEFERRED = "暂不申购"
    ARCHIVED = "已归档"
