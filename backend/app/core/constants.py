"""全局业务常量：跨模块复用的字面量，避免散落魔法值。"""

from datetime import timedelta, timezone

# 上海时区（业务时间展示/默认值基准）
SHANGHAI = timezone(timedelta(hours=8))

# 分页默认值
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200

# 导出行数上限
EXPORT_ROW_LIMIT = 10_000

# 申购计划默认值
DEFAULT_URGENCY = "正常"
DEFAULT_DEMAND_DEPARTMENT = "HXNI 检修维护部"
