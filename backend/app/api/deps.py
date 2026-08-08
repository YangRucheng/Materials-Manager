"""API 层共享依赖注入：跨路由文件重复的 Annotated 参数类型。"""

from typing import Annotated, Literal

from fastapi import Query

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]

StatusFilter = Annotated[str | None, Query(alias="status", max_length=128)]

SortOrder = Annotated[Literal["asc", "desc"], Query()]

OR_SEARCH_DESCRIPTION = "可使用 | 或 ｜ 分隔多个关键词，同一参数内匹配任意关键词"
OrSearch = Annotated[str | None, Query(description=OR_SEARCH_DESCRIPTION)]
OrSearch128 = Annotated[str | None, Query(max_length=128, description=OR_SEARCH_DESCRIPTION)]
OrSearch255 = Annotated[str | None, Query(max_length=255, description=OR_SEARCH_DESCRIPTION)]
