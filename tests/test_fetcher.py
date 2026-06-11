import httpx
import pytest

from backend.engine import fetcher


class DummyResponse:
    def __init__(self, content: bytes = b"ok", content_type: str = "text/plain"):
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None


@pytest.mark.asyncio
async def test_fetch_falls_back_to_curl_cffi_on_connect_error(monkeypatch):
    calls = []

    async def fake_httpx(*args, **kwargs):
        raise httpx.ConnectError("connect failed")

    async def fake_fallback(url, *, method, headers, body, first_error):
        calls.append((url, method, headers, body, type(first_error).__name__))
        return b"fallback", "text/plain; charset=utf-8"

    monkeypatch.setattr(fetcher, "_fetch_httpx", fake_httpx)
    monkeypatch.setattr(fetcher, "_fetch_with_curl_cffi", fake_fallback)

    text = await fetcher.fetch("https://example.com", use_cache=False)

    assert text == "fallback"
    assert calls[0][0] == "https://example.com"
    assert calls[0][4] == "ConnectError"


@pytest.mark.asyncio
async def test_fetch_does_not_fallback_for_http_status_errors(monkeypatch):
    async def fake_httpx(*args, **kwargs):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        return response

    async def fake_fallback(*args, **kwargs):
        raise AssertionError("fallback should not be called")

    monkeypatch.setattr(fetcher, "_fetch_httpx", fake_httpx)
    monkeypatch.setattr(fetcher, "_fetch_with_curl_cffi", fake_fallback)

    with pytest.raises(httpx.HTTPStatusError):
        await fetcher.fetch("https://example.com", use_cache=False)


@pytest.mark.asyncio
async def test_curl_cffi_retries_without_verify_only_for_tls_errors(monkeypatch):
    calls = []

    def fake_sync(url, method, headers, body, verify):
        calls.append(verify)
        if verify:
            raise RuntimeError("tls still bad")
        return b"unsafe-ok", "text/plain"

    monkeypatch.setattr(fetcher, "_fetch_with_curl_cffi_sync", fake_sync)

    content, _ = await fetcher._fetch_with_curl_cffi(
        "https://bad-cert.example",
        method="GET",
        headers={},
        body=None,
        first_error=httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]"),
    )

    assert content == b"unsafe-ok"
    assert calls == [True, False]
