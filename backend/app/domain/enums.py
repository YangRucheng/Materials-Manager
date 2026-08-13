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


class MiniProgramFeatureMode(StrEnum):
    DISABLED = "disabled"
    QUERY_ONLY = "query_only"
    READ_WRITE = "read_write"


class PurchasePlanStatus(StrEnum):
    NORMAL = "正常"
    DEFERRED = "暂不申购"
    ARCHIVED = "已归档"


class WebhookPlatform(StrEnum):
    FEISHU = "FEISHU"
    DINGTALK = "DINGTALK"


class WebhookEventType(StrEnum):
    STOCK_OUTBOUND_CREATED = "stock.outbound.created"
    STOCK_INBOUND_CREATED = "stock.inbound.created"
    MINI_PROGRAM_USER_BOUND = "mini_program.user.bound"


class WebhookDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ExcelImportJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
