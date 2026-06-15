from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.database import get_db
from backend.models.book import (
    BatchBookCategoryAssignSchema,
    BatchBookIdsSchema,
    BatchExportSchema,
    BookCategoryAssignSchema,
    BookCategoryCreateSchema,
    BookCategoryHiddenSchema,
    BookCategoryRenameSchema,
    BookCategorySchema,
    BookSchema,
    CacheClearSchema,
    DEFAULT_BOOK_CATEGORY_NAME,
    PUBLISHED_BOOK_CATEGORY_NAME,
)
from backend.services.book_manager import (
    clear_server_cache,
    delete_books_batch,
    ensure_book_cached,
    get_cache_stats,
    import_books_from_json,
    import_local_epub,
    import_local_txt,
)
from backend.services.exporter import export_book
from backend.config import settings
from backend.utils.book_key import build_book_key
from backend.utils.upload_guard import validate_upload_size

router = APIRouter(prefix="/api/books", tags=["books"])


def _normalize_category_name(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")
    return normalized


async def _category_exists(db, category_name: str) -> bool:
    cursor = await db.execute("SELECT name FROM book_categories WHERE name = ?", (category_name,))
    return await cursor.fetchone() is not None


async def _ensure_category_exists(db, category_name: str):
    await db.execute(
        """INSERT OR IGNORE INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        VALUES (?, 0, 0, datetime('now'), datetime('now'))""",
        (category_name,),
    )


async def _get_category_row(db, category_name: str):
    cursor = await db.execute(
        "SELECT name, hidden, preset FROM book_categories WHERE name = ?",
        (category_name,),
    )
    return await cursor.fetchone()


@router.get("/categories", response_model=list[BookCategorySchema])
async def list_book_categories():
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.name, c.hidden, c.preset, COUNT(b.id) AS book_count, c.created_at
        FROM book_categories c
        LEFT JOIN books b ON b.category_name = c.name
        GROUP BY c.name, c.hidden, c.preset, c.created_at
        ORDER BY
            CASE c.name
                WHEN '网文' THEN 0
                WHEN '出版' THEN 1
                ELSE 2
            END,
            c.created_at ASC,
            c.name COLLATE NOCASE ASC"""
    )
    rows = await cursor.fetchall()
    return [
        BookCategorySchema(
            name=row["name"],
            hidden=bool(row["hidden"]),
            preset=bool(row["preset"]),
            book_count=row["book_count"] or 0,
        )
        for row in rows
    ]


@router.post("/categories", response_model=BookCategorySchema)
async def create_book_category(payload: BookCategoryCreateSchema):
    db = await get_db()
    category_name = _normalize_category_name(payload.name)

    if await _category_exists(db, category_name):
        raise HTTPException(status_code=409, detail="Category already exists")

    await db.execute(
        """INSERT INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        VALUES (?, 0, 0, datetime('now'), datetime('now'))""",
        (category_name,),
    )
    await db.commit()
    return BookCategorySchema(name=category_name, hidden=False, preset=False, book_count=0)


@router.put("/categories/{category_name}/hidden")
async def set_book_category_hidden(category_name: str, payload: BookCategoryHiddenSchema):
    db = await get_db()
    normalized = _normalize_category_name(category_name)
    cursor = await db.execute(
        "UPDATE book_categories SET hidden = ?, updated_at = datetime('now') WHERE name = ?",
        (1 if payload.hidden else 0, normalized),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"name": normalized, "hidden": payload.hidden}


@router.put("/categories/{category_name}/rename")
async def rename_book_category(category_name: str, payload: BookCategoryRenameSchema):
    db = await get_db()
    old_name = _normalize_category_name(category_name)
    new_name = _normalize_category_name(payload.new_name)

    old_row = await _get_category_row(db, old_name)
    if not old_row:
        raise HTTPException(status_code=404, detail="Category not found")
    if bool(old_row["preset"]):
        raise HTTPException(status_code=400, detail="Preset category cannot be renamed")

    if old_name == new_name:
        return {"old_name": old_name, "new_name": new_name}

    if await _category_exists(db, new_name):
        raise HTTPException(status_code=409, detail="Target category already exists")

    await db.execute(
        "UPDATE books SET category_name = ?, updated_at = datetime('now') WHERE category_name = ?",
        (new_name, old_name),
    )
    await db.execute(
        "UPDATE book_categories SET name = ?, updated_at = datetime('now') WHERE name = ?",
        (new_name, old_name),
    )
    await db.commit()
    return {"old_name": old_name, "new_name": new_name}


@router.delete("/categories/{category_name}")
async def delete_book_category(category_name: str):
    db = await get_db()
    normalized = _normalize_category_name(category_name)
    row = await _get_category_row(db, normalized)
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")
    if bool(row["preset"]):
        raise HTTPException(status_code=400, detail="Preset category cannot be deleted")

    await _ensure_category_exists(db, DEFAULT_BOOK_CATEGORY_NAME)
    await db.execute(
        "UPDATE books SET category_name = ?, updated_at = datetime('now') WHERE category_name = ?",
        (DEFAULT_BOOK_CATEGORY_NAME, normalized),
    )
    cursor = await db.execute("DELETE FROM book_categories WHERE name = ?", (normalized,))
    await db.commit()
    return {
        "deleted": cursor.rowcount > 0,
        "name": normalized,
        "reassigned_to": DEFAULT_BOOK_CATEGORY_NAME,
    }


@router.get("", response_model=list[BookSchema])
async def list_books(
    include_hidden: bool = Query(default=False),
    category: str | None = Query(default=None),
):
    db = await get_db()
    sql = """SELECT
        b.*,
        COALESCE(cache_stats.server_cached_chapters, 0) AS server_cached_chapters
    FROM books b
    LEFT JOIN book_categories c ON c.name = b.category_name
    LEFT JOIN (
        SELECT book_id, COUNT(1) AS server_cached_chapters
        FROM chapter_cache
        GROUP BY book_id
    ) AS cache_stats ON cache_stats.book_id = b.id"""
    conditions = []
    params: list[str] = []

    # Exclude audiobooks from bookshelf
    conditions.append("b.source_url != 'local://audiobook'")

    if not include_hidden:
        conditions.append("COALESCE(c.hidden, 0) = 0")

    if category:
        normalized = _normalize_category_name(category)
        conditions.append("b.category_name = ?")
        params.append(normalized)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY b.updated_at DESC"

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [
        BookSchema(
            id=row["id"],
            book_key=row["book_key"] or "",
            name=row["name"],
            author=row["author"],
            cover_url=row["cover_url"] or "",
            intro=row["intro"] or "",
            book_url=row["book_url"],
            source_url=row["source_url"],
            category_name=row["category_name"] or DEFAULT_BOOK_CATEGORY_NAME,
            last_chapter=row["last_chapter"] or "",
            total_chapters=row["total_chapters"],
            server_cached_chapters=row["server_cached_chapters"] or 0,
            added_at=row["added_at"] or "",
            updated_at=row["updated_at"] or "",
        )
        for row in rows
    ]


@router.post("")
async def add_book(book: BookSchema):
    db = await get_db()
    book_key = book.book_key or build_book_key(book.source_url, book.book_url)
    if book.source_url.startswith("local://"):
        category_name = _normalize_category_name(book.category_name or PUBLISHED_BOOK_CATEGORY_NAME)
    else:
        # Books added via source flow always start in web-novel category.
        category_name = DEFAULT_BOOK_CATEGORY_NAME
    await _ensure_category_exists(db, category_name)

    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, category_name, last_chapter, total_chapters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(book_key) DO UPDATE SET
            name = excluded.name,
            author = excluded.author,
            cover_url = excluded.cover_url,
            intro = excluded.intro,
            book_url = excluded.book_url,
            source_url = excluded.source_url,
            last_chapter = excluded.last_chapter,
            total_chapters = excluded.total_chapters,
            updated_at = excluded.updated_at""",
        (
            book_key,
            book.name,
            book.author,
            book.cover_url,
            book.intro,
            book.book_url,
            book.source_url,
            category_name,
            book.last_chapter,
            book.total_chapters,
        ),
    )
    await db.commit()
    return {"message": "added"}


@router.put("/{book_id}/category")
async def set_book_category(book_id: int, payload: BookCategoryAssignSchema):
    db = await get_db()
    category_name = _normalize_category_name(payload.category_name)
    if not await _category_exists(db, category_name):
        raise HTTPException(status_code=404, detail="Category not found")

    cursor = await db.execute(
        "UPDATE books SET category_name = ?, updated_at = datetime('now') WHERE id = ?",
        (category_name, book_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"message": "updated", "book_id": book_id, "category_name": category_name}


@router.post("/category-batch")
async def set_book_category_batch(payload: BatchBookCategoryAssignSchema):
    db = await get_db()
    category_name = _normalize_category_name(payload.category_name)
    if not await _category_exists(db, category_name):
        raise HTTPException(status_code=404, detail="Category not found")

    if not payload.ids:
        return {"updated": 0, "requested": 0, "category_name": category_name}

    placeholders = ",".join("?" for _ in payload.ids)
    cursor = await db.execute(
        f"UPDATE books SET category_name = ?, updated_at = datetime('now') WHERE id IN ({placeholders})",
        [category_name, *payload.ids],
    )
    await db.commit()
    return {
        "updated": cursor.rowcount,
        "requested": len(payload.ids),
        "category_name": category_name,
    }


@router.delete("/{book_id}")
async def delete_book(book_id: int):
    db = await get_db()
    cursor = await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"message": "deleted"}


@router.post("/import")
async def import_books(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    raw = await validate_upload_size(file)
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        if suffix == ".json":
            result = await import_books_from_json(raw)
            return {"message": "imported", **result}
        if suffix == ".txt":
            result = await import_local_txt(file.filename or "import.txt", raw)
            return {"message": "imported", **result}
        if suffix == ".epub":
            result = await import_local_epub(file.filename or "import.epub", raw)
            return {"message": "imported", **result}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raise HTTPException(status_code=400, detail="Unsupported file type, use .json/.txt/.epub")


@router.post("/delete-batch")
async def delete_batch(payload: BatchBookIdsSchema):
    deleted = await delete_books_batch(payload.ids)
    return {"deleted": deleted, "requested": len(payload.ids)}


@router.post("/cache-batch")
async def cache_batch(payload: BatchBookIdsSchema):
    results = []
    for book_id in payload.ids:
        try:
            result = await ensure_book_cached(book_id)
        except Exception as exc:
            result = {
                "ok": False,
                "error": f"缓存失败: {str(exc)}",
            }
        results.append({"book_id": book_id, **result})

    success = sum(1 for item in results if item.get("ok"))
    return {"success": success, "total": len(results), "results": results}


@router.post("/export-batch")
async def export_batch(payload: BatchExportSchema):
    results = []
    for book_id in payload.ids:
        result = await export_book(book_id, payload.format)
        results.append(result)

    success = sum(1 for item in results if item.get("ok"))
    return {"success": success, "total": len(results), "format": payload.format, "results": results}


@router.get("/exports/{file_name}")
async def download_export(file_name: str):
    file_path = settings.export_dir / file_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(path=file_path, filename=file_name)


@router.get("/cache/stats")
async def cache_stats():
    stats = await get_cache_stats()
    return stats


@router.post("/cache/clear")
async def clear_cache(payload: CacheClearSchema):
    if payload.clear_all:
        cleared = await clear_server_cache()
    else:
        cleared = await clear_server_cache(payload.ids)
    return {"cleared": cleared, "clear_all": payload.clear_all}
