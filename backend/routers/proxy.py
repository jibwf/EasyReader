"""Image proxy — bypasses Referer + TLS fingerprint protection using curl_cffi."""

import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


def _fetch_image(url: str, referer: str) -> tuple[bytes, str] | None:
    """Fetch image using curl_cffi (browser TLS impersonation)."""
    try:
        from curl_cffi import requests
        r = requests.get(
            url,
            headers={"Referer": referer},
            impersonate="chrome120",
            timeout=20,
        )
        if r.status_code == 200:
            ct = r.headers.get("content-type", "image/jpeg")
            return (r.content, ct)
    except Exception:
        pass
    return None


@router.get("/image")
async def proxy_image(
    url: str = Query(...),
    referer: str = Query(default=""),
):
    if not url:
        return Response(status_code=400)

    parsed = urlparse(url)
    if not referer:
        referer = f"{parsed.scheme}://{parsed.netloc}/"

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch_image, url, referer)

    if not result:
        return Response(status_code=502)

    content, content_type = result
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )
