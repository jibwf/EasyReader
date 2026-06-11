import json
import re

from fastapi import APIRouter, Query, HTTPException

from backend.database import get_db
from backend.services.content import get_book_info, get_chapters, get_chapter_content
from backend.models.book import BookSchema, ChapterSchema

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/book-info", response_model=BookSchema)
async def book_info(
    book_key: str | None = Query(default=None),
    book_url: str | None = Query(default=None),
    source_url: str | None = Query(default=None),
):
    resolved_book_url, resolved_source_url = await _resolve_book_identity(
        book_key=book_key,
        book_url=book_url,
        source_url=source_url,
    )
    info = await get_book_info(resolved_book_url, resolved_source_url)
    if not info:
        raise HTTPException(status_code=404, detail="Book not found")
    return info


@router.get("/chapters", response_model=list[ChapterSchema])
async def chapters(
    book_key: str | None = Query(default=None),
    book_url: str | None = Query(default=None),
    source_url: str | None = Query(default=None),
):
    resolved_book_url, resolved_source_url = await _resolve_book_identity(
        book_key=book_key,
        book_url=book_url,
        source_url=source_url,
    )
    result = await get_chapters(resolved_book_url, resolved_source_url)
    return result


@router.get("/chapter")
async def chapter_content(
    url: str = Query(...),
    source_url: str = Query(...),
):
    content = await get_chapter_content(url, source_url)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check if content is a JSON array of image URLs (from Tauri manga sources)
    if content.strip().startswith("["):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list) and len(parsed) >= 1 and isinstance(parsed[0], str) and parsed[0].startswith("http"):
                return {"type": "manga", "images": parsed, "content": ""}
        except (json.JSONDecodeError, TypeError):
            pass

    images = _extract_images(content)
    if images:
        return {"type": "manga", "images": images, "content": ""}
    return {"type": "novel", "content": content, "images": []}


def _extract_images(content: str) -> list[str]:
    """Extract image URLs from content if it looks like manga."""
    # Check if content has multiple img tags
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    matches = img_pattern.findall(content)
    if len(matches) >= 3:
        return matches

    # Check for data-src or data-original patterns
    data_src_pattern = re.compile(r'(?:data-src|data-original)=["\']([^"\']+)["\']', re.IGNORECASE)
    data_matches = data_src_pattern.findall(content)
    if len(data_matches) >= 3:
        return data_matches

    # Check if content is newline-separated URLs (all starting with http)
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if len(lines) >= 3 and all(l.startswith("http") for l in lines[:5]):
        url_lines = [l for l in lines if l.startswith("http")]
        if len(url_lines) >= 3:
            return url_lines

    return []


async def _resolve_book_identity(
    *,
    book_key: str | None = None,
    book_url: str | None = None,
    source_url: str | None = None,
) -> tuple[str, str]:
    normalized_book_key = (book_key or "").strip()
    normalized_book_url = (book_url or "").strip()
    normalized_source_url = (source_url or "").strip()

    if normalized_book_key:
        db = await get_db()
        cursor = await db.execute(
            "SELECT book_url, source_url FROM books WHERE book_key = ?",
            (normalized_book_key,),
        )
        row = await cursor.fetchone()
        if row:
            return row["book_url"], row["source_url"]
        if normalized_book_url and normalized_source_url:
            return normalized_book_url, normalized_source_url
        raise HTTPException(status_code=404, detail="Book not found")

    if normalized_book_url and normalized_source_url:
        return normalized_book_url, normalized_source_url

    if normalized_book_url or normalized_source_url:
        raise HTTPException(status_code=400, detail="book_url and source_url are required together")

    raise HTTPException(status_code=400, detail="book_key or (book_url + source_url) is required")
