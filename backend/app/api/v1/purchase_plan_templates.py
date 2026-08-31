from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import OrSearch, OrSearch128, OrSearch255, PageNo, PageSize, SortOrder
from app.core.permissions import CurrentUser, DbSession, IfMatchVersion, PurchaseWriter
from app.schemas import (
    Page,
    PurchaseMaterialRead,
    PurchasePlanTemplateCreate,
    PurchasePlanTemplateFilterOptions,
    PurchasePlanTemplateRead,
    PurchasePlanTemplateUpdate,
)
from app.services import material_service
from app.services import purchase_plan_template_service as service

router = APIRouter(prefix="/purchase-plan-templates", tags=["周期性计划"])


@router.get("", response_model=Page[PurchasePlanTemplateRead])
async def list_templates(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: OrSearch = None,
    name: OrSearch128 = None,
    model_spec: OrSearch255 = None,
    actual_demand_person: OrSearch128 = None,
    purchase_responsible: OrSearch128 = None,
    category: Annotated[str | None, Query(max_length=64)] = None,
    sort_by: str | None = None,
    sort_order: SortOrder = "asc",
) -> Page[PurchasePlanTemplateRead]:
    items, total = await service.search_templates(
        session,
        keyword=keyword,
        name=name,
        model_spec=model_spec,
        actual_demand_person=actual_demand_person,
        purchase_responsible=purchase_responsible,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return Page(
        items=[service.template_read(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/filter-options", response_model=PurchasePlanTemplateFilterOptions)
async def filter_options(
    session: DbSession, user: CurrentUser
) -> PurchasePlanTemplateFilterOptions:
    (
        actual_demand_persons,
        purchase_responsibles,
        categories,
    ) = await service.template_filter_options(session)
    return PurchasePlanTemplateFilterOptions(
        actual_demand_persons=actual_demand_persons,
        purchase_responsibles=purchase_responsibles,
        categories=categories,
    )


@router.post("", response_model=PurchasePlanTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: PurchasePlanTemplateCreate, session: DbSession, user: PurchaseWriter
) -> PurchasePlanTemplateRead:
    return service.template_read(await service.create_template(session, data))


@router.get("/{template_id}", response_model=PurchasePlanTemplateRead)
async def template_detail(
    template_id: int, session: DbSession, user: CurrentUser
) -> PurchasePlanTemplateRead:
    return service.template_read(await service.get_template(session, template_id))


@router.patch("/{template_id}", response_model=PurchasePlanTemplateRead)
async def update_template(
    template_id: int,
    data: PurchasePlanTemplateUpdate,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchasePlanTemplateRead:
    template = await service.get_template(session, template_id)
    template = await service.update_template(session, template, data)
    return service.template_read(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    session: DbSession,
    user: PurchaseWriter,
    if_match: IfMatchVersion,
) -> None:
    template = await service.get_template(session, template_id)
    await service.delete_template(session, template, if_match)


@router.post("/{template_id}/generate", response_model=PurchaseMaterialRead)
async def generate_purchase_plan(
    template_id: int,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseMaterialRead:
    """把模板完整复制为一条今天的申购计划（plan_date=生成当天），模板本身不删除。"""
    template = await service.get_template(session, template_id)
    material = await service.generate_purchase_plan(session, template)
    return await material_service.purchase_read(session, material)
