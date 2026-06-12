import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_no_password_configured_allows_all(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_password_required_rejects_unauthenticated(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books")
        assert resp.status_code == 401
        assert "Invalid or missing authentication" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_version_endpoint_always_accessible(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/api/auth/login", json={"password": "secret123"})
        token = login_resp.json()["token"]

        resp = await client.get("/api/books", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
