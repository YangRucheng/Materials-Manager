"""周期性计划（申购计划模板）业务逻辑。

模板维护申购计划所需字段；「生成申购计划」把模板完整复制为一条新的
purchase_material（plan_no/plan_date/status 在生成时赋值，plan_date=生成当天），
模板本身不删除、可反复使用，也不改动既有申购计划。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SHANGHAI
from app.core.errors import AppError, not_found
from app.domain.enums import PurchasePlanStatus
from app.models import (
    FileObject,
    PurchaseMaterial,
    PurchaseMaterialImage,
    PurchasePlanTemplate,
    PurchasePlanTemplateImage,
    StockMaterial,
)
from app.repositories import purchase_plan_template_repository
from app.schemas import (
    PurchasePlanTemplateCreate,
    PurchasePlanTemplateRead,
    PurchasePlanTemplateUpdate,
)
from app.services.common import (
    file_read,
    utc_aware,
    validate_quantity_precision,
    validate_version,
)
from app.services.material_service import next_purchase_plan_no


async def _files(session: AsyncSession, image_ids: list[str]) -> list[FileObject]:
    if not image_ids:
        return []
    files = list(
        (await session.scalars(select(FileObject).where(FileObject.id.in_(image_ids)))).all()
    )
    by_id = {item.id: item for item in files}
    missing = [item_id for item_id in image_ids if item_id not in by_id]
    if missing:
        raise AppError("INVALID_IMAGE_ID", "图片不存在", details={"file_ids": missing})
    return [by_id[item_id] for item_id in image_ids]


async def _validate_stock_link(
    session: AsyncSession, stock_material_id: int | None
) -> StockMaterial | None:
    if stock_material_id is None:
        return None
    stock = await session.get(StockMaterial, stock_material_id)
    if stock is None:
        raise not_found("二级库物资")
    return stock


def _template_images(files: list[FileObject]) -> list[PurchasePlanTemplateImage]:
    return [
        PurchasePlanTemplateImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]


def _material_images(
    links: list[PurchasePlanTemplateImage],
) -> list[PurchaseMaterialImage]:
    """生成时按引用复制镜像：复用同一 file_id，不复制文件本体。"""
    return [
        PurchaseMaterialImage(
            file_id=link.file_id,
            file=link.file,
            sort_order=link.sort_order,
        )
        for link in links
    ]


def template_read(template: PurchasePlanTemplate) -> PurchasePlanTemplateRead:
    return PurchasePlanTemplateRead(
        id=template.id,
        material_code=template.material_code,
        category=template.category,
        urgency=template.urgency,
        demand_department=template.demand_department,
        name=template.name,
        model_spec=template.model_spec,
        unit_name=template.unit_name,
        actual_demand_person=template.actual_demand_person,
        purchase_responsible=template.purchase_responsible,
        planned_qty=template.planned_qty,
        usage=template.usage,
        subitem_no=template.subitem_no,
        remark=template.remark,
        stock_material_id=template.stock_material_id,
        stock_material_name=template.stock_material.name if template.stock_material else None,
        images=[file_read(link.file) for link in template.images],
        created_at=utc_aware(template.created_at),
        updated_at=utc_aware(template.updated_at),
        version=template.version,
    )


async def get_template(session: AsyncSession, template_id: int) -> PurchasePlanTemplate:
    template = await session.get(PurchasePlanTemplate, template_id)
    if template is None:
        raise not_found("周期性计划")
    return template


async def create_template(
    session: AsyncSession, data: PurchasePlanTemplateCreate
) -> PurchasePlanTemplate:
    responsible = data.purchase_responsible or "\\"
    validate_quantity_precision(data.planned_qty)
    stock = await _validate_stock_link(session, data.stock_material_id)
    files = await _files(session, data.image_ids)
    template = PurchasePlanTemplate(
        material_code=data.material_code,
        category=data.category,
        urgency=data.urgency,
        demand_department=data.demand_department,
        name=data.name,
        model_spec=data.model_spec,
        unit_name=data.unit_name,
        actual_demand_person=data.actual_demand_person or responsible,
        purchase_responsible=responsible,
        planned_qty=data.planned_qty,
        usage=data.usage,
        subitem_no=data.subitem_no,
        remark=data.remark,
        stock_material_id=data.stock_material_id,
        images=_template_images(files),
    )
    template.stock_material = stock
    session.add(template)
    await session.flush()
    return template


async def update_template(
    session: AsyncSession,
    template: PurchasePlanTemplate,
    data: PurchasePlanTemplateUpdate,
) -> PurchasePlanTemplate:
    validate_version(data.version, template.version)
    responsible = data.purchase_responsible or template.purchase_responsible
    validate_quantity_precision(data.planned_qty)
    stock = await _validate_stock_link(session, data.stock_material_id)
    files = await _files(session, data.image_ids)
    for key in (
        "material_code",
        "category",
        "urgency",
        "demand_department",
        "name",
        "model_spec",
        "unit_name",
        "planned_qty",
        "usage",
        "subitem_no",
        "remark",
        "stock_material_id",
    ):
        setattr(template, key, getattr(data, key))
    if data.actual_demand_person is not None:
        template.actual_demand_person = data.actual_demand_person
    template.purchase_responsible = responsible
    template.stock_material = stock
    template.images = _template_images(files)
    template.version += 1
    await session.flush()
    return template


async def delete_template(
    session: AsyncSession, template: PurchasePlanTemplate, version: int | None
) -> None:
    validate_version(version, template.version)
    await session.delete(template)
    await session.flush()


async def generate_purchase_plan(
    session: AsyncSession, template: PurchasePlanTemplate
) -> PurchaseMaterial:
    """把模板完整复制为一条今天的申购计划（plan_date=生成当天）。模板不改动、不删除。"""
    today = datetime.now(SHANGHAI).date()
    material = PurchaseMaterial(
        plan_no=await next_purchase_plan_no(session, today),
        plan_date=today,
        material_code=template.material_code,
        category=template.category,
        urgency=template.urgency,
        demand_department=template.demand_department,
        name=template.name,
        model_spec=template.model_spec,
        unit_name=template.unit_name,
        actual_demand_person=template.actual_demand_person,
        purchase_responsible=template.purchase_responsible,
        planned_qty=template.planned_qty,
        usage=template.usage,
        subitem_no=template.subitem_no,
        remark=template.remark,
        stock_material_id=template.stock_material_id,
        status=PurchasePlanStatus.NORMAL,
        images=_material_images(template.images),
    )
    material.stock_material = template.stock_material
    session.add(material)
    await session.flush()
    return material


async def search_templates(
    session: AsyncSession,
    *,
    keyword: str | None,
    name: str | None,
    model_spec: str | None,
    actual_demand_person: str | None,
    purchase_responsible: str | None,
    category: str | None,
    page: int,
    page_size: int,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[PurchasePlanTemplate], int]:
    return await purchase_plan_template_repository.search_templates(
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


async def template_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str], list[str]]:
    return await purchase_plan_template_repository.template_filter_options(session)
