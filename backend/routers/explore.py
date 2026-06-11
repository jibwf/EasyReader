"""Explore/ranking endpoint — fetches popular books by category and time period."""

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.utils.book_key import build_book_key

router = APIRouter(prefix="/api/explore", tags=["explore"])

CATEGORIES = {
    "xuanhuan": "玄幻",
    "dushi": "都市",
    "xianxia": "仙侠",
    "yanqing": "言情",
    "kehuan": "科幻",
    "lishi": "历史",
    "wuxia": "武侠",
    "xiuzhen": "修真",
    "chuanyue": "穿越",
}

SOURCE_URL = "http://www.shukuge.com"


class RankItem(BaseModel):
    book_key: str
    name: str
    book_url: str
    source_url: str


@router.get("/ranking", response_model=list[RankItem])
async def get_ranking(
    category: str = Query(default="xuanhuan"),
    period: str = Query(default="week"),
):
    if category not in CATEGORIES:
        category = "xuanhuan"

    # 365book uses /top/category/ for all-time, /i-category/ for category pages
    # For period filtering we use the same page but vary the URL pattern
    if period == "week":
        url = f"{SOURCE_URL}/i-{category}/"
    elif period == "month":
        url = f"{SOURCE_URL}/top/{category}/"
    else:
        url = f"{SOURCE_URL}/top/{category}/"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0", "Referer": f"{SOURCE_URL}/"}
            )
            resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    seen = set()
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text().strip()
        if (
            text
            and "/book/" in href
            and "/index.html" not in href
            and href not in seen
            and len(text) < 30
        ):
            seen.add(href)
            full_url = f"{SOURCE_URL}{href}" if href.startswith("/") else href
            results.append(
                RankItem(
                    book_key=build_book_key(SOURCE_URL, full_url),
                    name=text,
                    book_url=full_url,
                    source_url=SOURCE_URL,
                )
            )
            if len(results) >= 20:
                break

    return results


@router.get("/manga-ranking", response_model=list[RankItem])
async def get_manga_ranking(category: str = Query(default="全部漫画")):
    """Get manga ranking from Tauri sources (G-site explore)."""
    import asyncio
    from backend.services.source_manager import get_source_raw
    from backend.engine.js_engine import TauriEngine

    # Use G-site manga source
    manga_source_url = "https://m.g-mh.org/"
    raw = await get_source_raw(manga_source_url)
    if not raw or raw[1] != "tauri":
        return []

    source_code = raw[0]

    def run_explore():
        engine = TauriEngine(source_code, manga_source_url)
        return engine.call("explore", 1, category)

    loop = asyncio.get_event_loop()
    try:
        result_json = await loop.run_in_executor(None, run_explore)
    except Exception:
        return []

    import json
    try:
        data = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        return []

    results = []
    for item in data[:20]:
        name = item.get("name") or item.get("title") or ""
        book_url = item.get("bookUrl") or item.get("tocUrl") or ""
        source_url = manga_source_url
        if name and book_url:
            results.append(
                RankItem(
                    book_key=build_book_key(source_url, book_url),
                    name=name,
                    book_url=book_url,
                    source_url=source_url,
                )
            )

    return results
