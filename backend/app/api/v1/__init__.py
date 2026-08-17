from fastapi import APIRouter

from app.api.v1 import (
    ai_search,
    auth,
    dictionaries,
    excel_export_jobs,
    files,
    huaxing_inventory,
    inventory,
    material_code_library,
    mini_program,
    purchase_materials,
    purchase_record_sync,
    purchase_requests,
    stock_materials,
    system_settings,
    version,
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
router.include_router(ai_search.router)
router.include_router(system_settings.router)
router.include_router(stock_materials.router)
router.include_router(inventory.router)
router.include_router(material_code_library.router)
router.include_router(huaxing_inventory.router)
router.include_router(mini_program.management_router)
router.include_router(mini_program.mini_router)
router.include_router(purchase_materials.router)
router.include_router(purchase_record_sync.router)
router.include_router(purchase_requests.router)
router.include_router(dictionaries.router)
router.include_router(excel_export_jobs.router)
router.include_router(files.router)
router.include_router(version.router)
