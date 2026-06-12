import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_no_api_key_configured_allows_all(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(api_key="", password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_key_required_rejects_missing(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123", password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books")
        assert resp.status_code == 401
        assert "Invalid or missing authentication" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_required_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123", password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books", headers={"x-api-key": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_required_accepts_correct_key(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123", password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books", headers={"x-api-key": "secret123"})
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_version_endpoint_always_accessible(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123", password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200
