import json
import re

from fastapi import APIRouter, Query, HTTPException

from backend.database import get_db
from backend.services.content import get_book_info, get_chapters, get_chapter_content
from backend.models.book import BookSchema, ChapterSchema

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/book-info", response_model=BookSchema)
async def book_info(
    book_key: str = Query(...),
):
    book_url, source_url = await _resolve_book_identity(book_key=book_key)
    info = await get_book_info(book_url, source_url)
    if not info:
        raise HTTPException(status_code=404, detail="Book not found")
    return info


@router.get("/chapters", response_model=list[ChapterSchema])
async def chapters(
    book_key: str = Query(...),
):
    book_url, source_url = await _resolve_book_identity(book_key=book_key)
    result = await get_chapters(book_url, source_url)
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
    book_key: str,
) -> tuple[str, str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT book_url, source_url FROM books WHERE book_key = ?",
        (book_key,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return row["book_url"], row["source_url"]
