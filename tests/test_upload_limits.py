import io
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_books_import_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(max_upload_size_mb=1))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        large_content = b"x" * (2 * 1024 * 1024)
        resp = await client.post(
            "/api/books/import",
            files={"file": ("test.txt", io.BytesIO(large_content), "text/plain")},
        )
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_books_import_accepts_valid_file(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(max_upload_size_mb=1))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        small_content = b'{"books": []}'
        resp = await client.post(
            "/api/books/import",
            files={"file": ("test.json", io.BytesIO(small_content), "application/json")},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sources_import_rejects_long_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sources = [{"book_source_url": f"http://example.com/{i}"} for i in range(1001)]
        resp = await client.post("/api/sources/import", json=sources)
        assert resp.status_code == 413
        assert "List too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sources_import_accepts_valid_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sources = [{"book_source_url": f"http://example.com/{i}"} for i in range(100)]
        resp = await client.post("/api/sources/import", json=sources)
        assert resp.status_code == 200
