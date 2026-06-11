import hashlib
import json
import asyncio
from pathlib import Path

import httpx
from charset_normalizer import from_bytes

from backend.config import settings

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            follow_redirects=True,
            proxy=settings.proxy,
            headers={"User-Agent": settings.user_agent},
        )
    return _client


def _cache_key(url: str, method: str, body: str | None) -> str:
    raw = f"{method}:{url}:{body or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    d = settings.content_cache_dir / key[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / key


async def fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
    use_cache: bool = True,
    encoding: str | None = None,
) -> str:
    if use_cache:
        key = _cache_key(url, method, body)
        path = _cache_path(key)
        if path.exists():
            return path.read_text(encoding="utf-8")

    merged_headers = _merge_headers(url, headers)
    try:
        resp = await _fetch_httpx(url, method=method, headers=merged_headers, body=body)
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("content-type", "")
    except _fallback_exceptions() as first_error:
        content, content_type = await _fetch_with_curl_cffi(
            url,
            method=method,
            headers=merged_headers,
            body=body,
            first_error=first_error,
        )

    if encoding:
        text = content.decode(encoding, errors="replace")
    else:
        text = _detect_encoding(content, content_type)

    if use_cache and len(text) > 50:
        key = _cache_key(url, method, body)
        path = _cache_path(key)
        path.write_text(text, encoding="utf-8")

    return text


def _merge_headers(url: str, headers: dict | None) -> dict:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    merged_headers = {"User-Agent": settings.user_agent, "Referer": referer}
    if headers:
        merged_headers.update({str(key): str(value) for key, value in headers.items() if value is not None})
    return merged_headers


async def _fetch_httpx(url: str, *, method: str, headers: dict, body: str | None) -> httpx.Response:
    client = _get_client()
    if method.upper() == "POST":
        return await client.post(url, headers=headers, content=body)
    return await client.get(url, headers=headers)


def _fallback_exceptions():
    return (
        httpx.ConnectError,
        httpx.RemoteProtocolError,
    )


async def _fetch_with_curl_cffi(
    url: str,
    *,
    method: str,
    headers: dict,
    body: str | None,
    first_error: Exception,
) -> tuple[bytes, str]:
    try:
        return await asyncio.to_thread(
            _fetch_with_curl_cffi_sync,
            url,
            method,
            headers,
            body,
            True,
        )
    except Exception:
        if "CERTIFICATE_VERIFY_FAILED" not in str(first_error):
            raise first_error
        return await asyncio.to_thread(
            _fetch_with_curl_cffi_sync,
            url,
            method,
            headers,
            body,
            False,
        )


def _fetch_with_curl_cffi_sync(
    url: str,
    method: str,
    headers: dict,
    body: str | None,
    verify: bool,
) -> tuple[bytes, str]:
    from curl_cffi import requests as cf_requests

    request = cf_requests.post if method.upper() == "POST" else cf_requests.get
    response = request(
        url,
        headers=headers,
        data=body if method.upper() == "POST" else None,
        impersonate="chrome120",
        timeout=settings.request_timeout,
        allow_redirects=True,
        verify=verify,
    )
    response.raise_for_status()
    content = response.content
    if isinstance(content, str):
        content = content.encode(response.encoding or "utf-8", errors="replace")
    return content, response.headers.get("content-type", "")


def _detect_encoding(content: bytes, content_type: str) -> str:
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            return content.decode(charset, errors="replace")
        except (UnicodeDecodeError, LookupError):
            pass

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass

    result = from_bytes(content).best()
    if result:
        return str(result)

    return content.decode("utf-8", errors="replace")


def parse_headers(header_str: str) -> dict:
    if not header_str:
        return {}
    try:
        headers = json.loads(header_str)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(headers, dict):
        return {}
    return {str(key): str(value) for key, value in headers.items() if value is not None}


async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None
