from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from PIL import Image

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_uploaded_image_is_reencoded_as_png(client: AsyncClient) -> None:
    headers = await auth_headers(client, "warehouse")
    source = io.BytesIO()
    Image.new("RGB", (16, 12), "red").save(source, format="JPEG", exif=b"Exif\x00\x00metadata")
    response = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("source.jpg", source.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mime_type"] == "image/png"
    downloaded = await client.get(body["url"], headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"\x89PNG\r\n\x1a\n")
