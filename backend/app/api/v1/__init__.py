from fastapi import APIRouter

from app.api.v1 import (
    agent_database,
    auth,
    dictionaries,
    files,
    inventory,
    purchase_materials,
    purchase_requests,
    stock_materials,
)
from app.schemas import ApiError

router = APIRouter(
    responses={
        400: {"model": ApiError, "description": "业务校验失败"},
        401: {"model": ApiError, "description": "未认证或凭证无效"},
        403: {"model": ApiError, "description": "权限不足"},
        409: {"model": ApiError, "description": "版本、状态或业务数据冲突"},
        422: {"model": ApiError, "description": "请求参数校验失败"},
    }
)
router.include_router(auth.router)
router.include_router(agent_database.router)
router.include_router(stock_materials.router)
router.include_router(inventory.router)
router.include_router(purchase_materials.router)
router.include_router(purchase_requests.router)
router.include_router(dictionaries.router)
router.include_router(files.router)
