from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.models import (
    FileObject,
    PurchaseMaterialImage,
    StockMaterialImage,
)
from app.schemas import FileObjectRead
from app.services.common import file_read

ACCEPTED_TYPES = {"image/jpeg", "image/png", "image/webp"}


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
    file_name = f"{uuid.uuid4()}.png"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / file_name
    target.write_bytes(data)
    item = FileObject(
        file_name=file_name,
        original_name=Path(upload.filename or "image").name[:255],
        relative_path=f"data/uploads/{file_name}",
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
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return file_read(item)


async def get_image(session: AsyncSession, file_id: int) -> tuple[FileObject, Path]:
    item = await session.get(FileObject, file_id)
    if item is None:
        raise not_found("图片")
    path = settings.upload_dir / item.file_name
    if not path.is_file():
        raise AppError("FILE_MISSING", "图片文件不存在", status_code=404)
    return item, path


async def delete_image(session: AsyncSession, file_id: int) -> None:
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
    path = settings.upload_dir / item.file_name
    await session.delete(item)
    await session.flush()
    path.unlink(missing_ok=True)
