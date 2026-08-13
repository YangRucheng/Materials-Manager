from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.domain.enums import ExcelImportJobStatus
from app.models import ExcelImportJob
from app.services import import_job_service
from tests.conftest import auth_headers


def build_workbook(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["状态", "编码", "名称", "记账单位名称", "型号", "其他列"])
    for row in rows:
        worksheet.append(row)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return content.getvalue()


async def _insert_job(
    *,
    import_type: str,
    status: ExcelImportJobStatus,
    file_path: str,
) -> int:
    async with SessionLocal() as session:
        job = ExcelImportJob(
            import_type=import_type,
            status=status,
            original_filename="test.xlsx",
            file_path=file_path,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


@pytest.mark.asyncio
async def test_mark_stale_jobs_failed_marks_interrupted_and_unlinks(
    client: AsyncClient, tmp_path
) -> None:
    paths = [tmp_path / f"f{i}.xlsx" for i in range(4)]
    for path in paths:
        path.write_bytes(b"x")
    statuses = [
        ExcelImportJobStatus.PENDING,
        ExcelImportJobStatus.RUNNING,
        ExcelImportJobStatus.SUCCEEDED,
        ExcelImportJobStatus.FAILED,
    ]
    async with SessionLocal() as session:
        for status, path in zip(statuses, paths, strict=False):
            session.add(
                ExcelImportJob(
                    import_type="STALE_TEST",
                    status=status,
                    original_filename="t.xlsx",
                    file_path=str(path),
                )
            )
        await session.commit()

    count = await import_job_service.mark_stale_jobs_failed()

    assert count == 2
    async with SessionLocal() as session:
        rows = list(
            (await session.scalars(select(ExcelImportJob).order_by(ExcelImportJob.id))).all()
        )
    assert [row.status for row in rows] == [
        ExcelImportJobStatus.FAILED,
        ExcelImportJobStatus.FAILED,
        ExcelImportJobStatus.SUCCEEDED,
        ExcelImportJobStatus.FAILED,
    ]
    assert rows[0].error_code == "SERVER_RESTARTED"
    assert rows[1].error_code == "SERVER_RESTARTED"
    assert rows[2].error_code is None
    assert rows[3].error_code is None
    for index, path in enumerate(paths):
        assert path.exists() == (index >= 2)


@pytest.mark.asyncio
async def test_import_rejected_when_active_job_exists(client: AsyncClient) -> None:
    await _insert_job(
        import_type="MATERIAL_CODE_LIBRARY",
        status=ExcelImportJobStatus.PENDING,
        file_path="unused.xlsx",
    )
    headers = await auth_headers(client, "purchase")
    response = await client.post(
        "/api/v1/material-code-library/import",
        headers=headers,
        files={
            "file": (
                "codes.xlsx",
                build_workbook([["生效", "Y001", "按钮", "个", "LA38", ""]]),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "IMPORT_IN_PROGRESS"


@pytest.mark.asyncio
async def test_run_job_success_marks_succeeded(client: AsyncClient, tmp_path) -> None:
    target = tmp_path / "job.xlsx"
    target.write_bytes(b"x")

    async def ok_processor(file_path: Path) -> dict[str, object]:
        assert file_path == target
        return {"imported_count": 7}

    job_id = await _insert_job(
        import_type="UNIT", status=ExcelImportJobStatus.PENDING, file_path=str(target)
    )
    await import_job_service._run_job(job_id, ok_processor)

    async with SessionLocal() as session:
        job = await session.get(ExcelImportJob, job_id)
    assert job is not None
    assert job.status == ExcelImportJobStatus.SUCCEEDED
    assert job.result == {"imported_count": 7}
    assert job.error_code is None
    assert not target.exists()


@pytest.mark.asyncio
async def test_run_job_app_error_marks_failed(client: AsyncClient, tmp_path) -> None:
    target = tmp_path / "job.xlsx"
    target.write_bytes(b"x")

    async def failing_processor(file_path: Path) -> dict[str, object]:
        raise AppError("TEST_APP_ERROR", "模拟解析失败")

    job_id = await _insert_job(
        import_type="UNIT", status=ExcelImportJobStatus.PENDING, file_path=str(target)
    )
    await import_job_service._run_job(job_id, failing_processor)

    async with SessionLocal() as session:
        job = await session.get(ExcelImportJob, job_id)
    assert job is not None
    assert job.status == ExcelImportJobStatus.FAILED
    assert job.error_code == "TEST_APP_ERROR"
    assert job.error_message == "模拟解析失败"
    assert not target.exists()


@pytest.mark.asyncio
async def test_run_job_unexpected_error_marks_failed(client: AsyncClient, tmp_path) -> None:
    target = tmp_path / "job.xlsx"
    target.write_bytes(b"x")

    async def crashing_processor(file_path: Path) -> dict[str, object]:
        raise RuntimeError("boom")

    job_id = await _insert_job(
        import_type="UNIT", status=ExcelImportJobStatus.PENDING, file_path=str(target)
    )
    await import_job_service._run_job(job_id, crashing_processor)

    async with SessionLocal() as session:
        job = await session.get(ExcelImportJob, job_id)
    assert job is not None
    assert job.status == ExcelImportJobStatus.FAILED
    assert job.error_code == "INTERNAL_IMPORT_ERROR"
    assert job.error_message == "导入任务发生未知错误"
    assert not target.exists()
