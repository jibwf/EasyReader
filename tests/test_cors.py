import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


def test_cors_origin_list_wildcard():
    s = Settings(cors_origins="*")
    assert s.cors_origin_list == ["*"]


def test_cors_origin_list_multiple():
    s = Settings(cors_origins="http://localhost:5173,https://example.com")
    assert s.cors_origin_list == ["http://localhost:5173", "https://example.com"]


def test_cors_origin_list_empty():
    s = Settings(cors_origins="")
    assert s.cors_origin_list == []


def test_cors_origin_list_strips_whitespace():
    s = Settings(cors_origins=" http://a.com , https://b.com ")
    assert s.cors_origin_list == ["http://a.com", "https://b.com"]


@pytest.mark.asyncio
async def test_cors_default_allows_origins():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/api/books",
            headers={
                "Origin": "http://any.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "*"
