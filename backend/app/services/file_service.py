from __future__ import annotations

import asyncio
import hashlib
import io
import re
from datetime import UTC, timedelta
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.core.identifiers import uuid7_string
from app.models import (
    FileObject,
    PurchaseMaterialImage,
    StockMaterialImage,
)
from app.schemas import (
    FileObjectRead,
    OrphanFileCleanupRead,
    OrphanFileRead,
    OrphanFileReportRead,
)
from app.services.common import file_read, utc_aware, utcnow

ACCEPTED_TYPES = {"image/jpeg", "image/png", "image/webp"}
PREVIEW_MIME_TYPE = "image/webp"
MANAGED_FILE_NAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.png$"
)


def file_path(file_id: str) -> Path:
    return settings.upload_dir / f"{file_id}.png"


def _unreferenced() -> ColumnElement[bool]:
    return ~exists().where(StockMaterialImage.file_id == FileObject.id) & ~exists().where(
        PurchaseMaterialImage.file_id == FileObject.id
    )


def _managed_disk_files() -> dict[str, Path]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return {
        path.name: path
        for path in settings.upload_dir.iterdir()
        if path.is_file() and MANAGED_FILE_NAME.fullmatch(path.name)
    }


def _render_preview(source: Path, size: int) -> bytes:
    output = io.BytesIO()
    with Image.open(source) as image:
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        converted.save(output, format="WEBP", quality=82, method=6)
    return output.getvalue()


async def save_image(session: AsyncSession, upload: UploadFile, user_id: int) -> FileObjectRead:
    if upload.content_type not in ACCEPTED_TYPES:
        raise AppError("INVALID_IMAGE_TYPE", "仅支持 JPEG、PNG 或 WebP 图片")
    raw = await upload.read(settings.max_image_bytes + 1)
    if len(raw) > settings.max_image_bytes:
        raise AppError("IMAGE_TOO_LARGE", "单张图片不能超过 10 MB", status_code=413)
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            converted = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            width, height = converted.size
            output = io.BytesIO()
            converted.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError("INVALID_IMAGE", "图片无法解码") from exc

    data = output.getvalue()
    file_id = uuid7_string()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = file_path(file_id)
    await asyncio.to_thread(target.write_bytes, data)
    item = FileObject(
        id=file_id,
        original_name=Path(upload.filename or "image").name[:255],
        mime_type="image/png",
        size_bytes=len(data),
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(item)
    try:
        await session.flush()
        # 上传是独立事务。只有数据库记录真正提交后才向客户端返回成功。
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(target.unlink, missing_ok=True)
        raise
    return file_read(item)


async def get_image(session: AsyncSession, file_id: str) -> tuple[FileObject, Path]:
    item = await session.get(FileObject, file_id)
    if item is None:
        raise not_found("图片")
    path = file_path(file_id)
    if not path.is_file():
        raise AppError("FILE_MISSING", "图片文件不存在")
    return item, path


async def render_preview(path: Path, size: int) -> bytes:
    try:
        return await asyncio.to_thread(_render_preview, path, size)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError("INVALID_IMAGE", "图片无法生成预览") from exc


async def delete_image(session: AsyncSession, file_id: str) -> None:
    item = await session.get(FileObject, file_id)
    if item is None:
        raise not_found("图片")
    referenced = False
    for model in (StockMaterialImage, PurchaseMaterialImage):
        if await session.scalar(select(exists().where(model.file_id == file_id))):
            referenced = True
            break
    if referenced:
        raise AppError("FILE_IN_USE", "图片已被业务引用，不能删除", status_code=409)
    path = file_path(file_id)
    await session.delete(item)
    await session.commit()
    await asyncio.to_thread(path.unlink, missing_ok=True)


async def inspect_orphans(
    session: AsyncSession, older_than_hours: int
) -> OrphanFileReportRead:
    cutoff = utcnow() - timedelta(hours=older_than_hours)
    unreferenced = list(
        (
            await session.scalars(
                select(FileObject)
                .where(FileObject.created_at <= cutoff, _unreferenced())
                .order_by(FileObject.created_at, FileObject.id)
            )
        ).all()
    )
    all_records = list(
        (await session.execute(select(FileObject.id, FileObject.created_at))).all()
    )
    disk_files = await asyncio.to_thread(_managed_disk_files)
    cutoff_timestamp = cutoff.replace(tzinfo=UTC).timestamp()
    record_ids = {file_id for file_id, _ in all_records}
    untracked = sorted(
        name
        for name, path in disk_files.items()
        if name.removesuffix(".png") not in record_ids and path.stat().st_mtime <= cutoff_timestamp
    )
    missing = sorted(
        file_id
        for file_id, created_at in all_records
        if created_at <= cutoff and f"{file_id}.png" not in disk_files
    )
    return OrphanFileReportRead(
        cutoff=utc_aware(cutoff),
        unreferenced_records=[
            OrphanFileRead(
                id=item.id,
                original_name=item.original_name,
                size_bytes=item.size_bytes,
                created_at=utc_aware(item.created_at),
                file_exists=f"{item.id}.png" in disk_files,
            )
            for item in unreferenced
        ],
        untracked_file_names=untracked,
        missing_file_ids=missing,
    )


async def cleanup_orphans(
    session: AsyncSession, older_than_hours: int
) -> OrphanFileCleanupRead:
    report = await inspect_orphans(session, older_than_hours)
    record_ids = [item.id for item in report.unreferenced_records]
    if record_ids:
        records = list(
            (
                await session.scalars(
                    select(FileObject).where(FileObject.id.in_(record_ids), _unreferenced())
                )
            ).all()
        )
        deleted_record_ids = [item.id for item in records]
        for item in records:
            await session.delete(item)
        await session.commit()
    else:
        deleted_record_ids = []

    candidates = [f"{file_id}.png" for file_id in deleted_record_ids]
    candidates.extend(report.untracked_file_names)
    deleted_file_names: list[str] = []
    for name in sorted(set(candidates)):
        path = settings.upload_dir / name
        if path.is_file():
            await asyncio.to_thread(path.unlink)
            deleted_file_names.append(name)
    return OrphanFileCleanupRead(
        cutoff=report.cutoff,
        deleted_record_ids=deleted_record_ids,
        deleted_file_names=deleted_file_names,
    )
