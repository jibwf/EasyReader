import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_login_with_correct_password(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"password": "test123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["expires_in_days"] == 90


@pytest.mark.asyncio
async def test_login_with_wrong_password(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_valid_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/api/auth/login", json={"password": "test123"})
        token = login_resp.json()["token"]

        resp = await client.get(f"/api/auth/verify?token={token}")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/api/auth/login", json={"password": "test123"})
        token = login_resp.json()["token"]

        resp = await client.get("/api/books", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
