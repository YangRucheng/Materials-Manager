from __future__ import annotations

import logging

from pytest import LogCaptureFixture
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError, TimeoutError
from starlette.requests import Request

from app.main import (
    handle_database_error,
    handle_database_programming_error,
    handle_database_unavailable,
)


def request_with_id(request_id: str = "request-123") -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/test", "headers": []})
    request.state.request_id = request_id
    return request


async def test_programming_error_is_not_reported_as_database_unavailable(
    caplog: LogCaptureFixture,
) -> None:
    error = ProgrammingError("SELECT usage FROM purchase_material", {}, Exception("syntax"))

    with caplog.at_level(logging.ERROR, logger="spare_parts.api"):
        response = await handle_database_programming_error(request_with_id(), error)

    assert response.status_code == 500
    assert b'"code":"DATABASE_QUERY_ERROR"' in response.body
    assert "database query error request_id=request-123" in caplog.text
    assert "sqlalchemy.exc.ProgrammingError" in caplog.text


async def test_database_timeout_is_reported_as_unavailable() -> None:
    response = await handle_database_unavailable(request_with_id(), TimeoutError("pool timeout"))

    assert response.status_code == 503
    assert b'"code":"DATABASE_UNAVAILABLE"' in response.body


async def test_mysql_unknown_column_operational_error_is_reported_as_query_error() -> None:
    original = Exception(1054, "Unknown column 'material_code' in 'field list'")
    error = OperationalError("SELECT material_code FROM purchase_request", {}, original)

    response = await handle_database_unavailable(request_with_id(), error)

    assert response.status_code == 500
    assert b'"code":"DATABASE_QUERY_ERROR"' in response.body


async def test_mysql_connection_operational_error_is_reported_as_unavailable() -> None:
    original = Exception(2003, "Can't connect to MySQL server")
    error = OperationalError("SELECT 1", {}, original)

    response = await handle_database_unavailable(request_with_id(), error)

    assert response.status_code == 503
    assert b'"code":"DATABASE_UNAVAILABLE"' in response.body


async def test_other_sqlalchemy_errors_are_internal_database_errors() -> None:
    response = await handle_database_error(request_with_id(), SQLAlchemyError("bad state"))

    assert response.status_code == 500
    assert b'"code":"DATABASE_ERROR"' in response.body
