import asyncio
import hashlib
import io
import json
from pathlib import Path
import re
from pathlib import PurePosixPath

from bs4 import BeautifulSoup
from charset_normalizer import from_bytes

from backend.database import get_db
from backend.models.book import BookImportItemSchema, PUBLISHED_BOOK_CATEGORY_NAME
from backend.services.content import get_chapter_content, get_chapters
from backend.utils.book_key import build_book_key


def _make_local_book_url(prefix: str, content: bytes) -> str:
    digest = hashlib.sha1(content).hexdigest()
    return f"local://{prefix}/{digest}"


def _safe_filename(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", " ")).strip() or "book"


def _normalize_epub_title(value: str) -> str:
    text = " ".join((value or "").replace("\xa0", " ").split()).strip()
    if not text:
        return ""

    if "/" in text or text.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
        text = PurePosixPath(text).name

    text = re.sub(r"\.(xhtml|html|htm|xml)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_epub_chapter_title(item_name: str, soup: BeautifulSoup, text: str) -> str:
    file_title = _normalize_epub_title(item_name)

    for heading_name in ("h1", "h2", "h3"):
        heading = soup.find(heading_name)
        if not heading:
            continue

        heading_title = _normalize_epub_title(heading.get_text(" ", strip=True))
        if heading_title:
            return heading_title

    page_title = ""
    if soup.title and soup.title.string:
        page_title = _normalize_epub_title(soup.title.string)
    if page_title and page_title.lower() != file_title.lower():
        return page_title

    for raw_line in text.splitlines():
        line = _normalize_epub_title(raw_line)
        if not line or line.lower() == file_title.lower():
            continue
        if len(line) <= 80:
            return line

    return file_title or "Untitled Chapter"


async def _get_book_id(db, book_url: str, source_url: str) -> int:
    cursor = await db.execute(
        "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
        (book_url, source_url),
    )
    row = await cursor.fetchone()
    return row["id"]


async def import_books_from_json(raw_json: bytes) -> dict:
    try:
        parsed = json.loads(raw_json.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid JSON file") from exc

    items = parsed if isinstance(parsed, list) else [parsed]
    imported = 0
    failed = 0

    db = await get_db()
    for item in items:
        try:
            payload = BookImportItemSchema.model_validate(item)
        except Exception:
            failed += 1
            continue

        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(book_key) DO UPDATE SET
                name = excluded.name,
                author = excluded.author,
                cover_url = excluded.cover_url,
                intro = excluded.intro,
                book_url = excluded.book_url,
                source_url = excluded.source_url,
                updated_at = excluded.updated_at""",
            (
                build_book_key(payload.source_url, payload.book_url),
                payload.name,
                payload.author,
                payload.cover_url,
                payload.intro,
                payload.book_url,
                payload.source_url,
            ),
        )
        imported += 1

    await db.commit()
    return {"imported": imported, "failed": failed}


def _text_quality_score(text: str) -> float:
    if not text:
        return float("-inf")

    total = len(text)
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    replacement = text.count("\ufffd")
    null_bytes = text.count("\x00")
    controls = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")

    printable_ratio = printable / total
    cjk_ratio = cjk / total

    return (printable_ratio * 100.0) + (cjk_ratio * 30.0) - (replacement * 5.0) - (null_bytes * 20.0) - (controls * 2.0)


def _decode_local_txt(raw_content: bytes) -> str:
    if not raw_content:
        return ""

    decoded_candidates: list[str] = []
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk", "big5"):
        try:
            decoded_candidates.append(raw_content.decode(encoding))
        except UnicodeDecodeError:
            continue

    try:
        detected = from_bytes(raw_content).best()
        if detected is not None:
            decoded_candidates.append(str(detected))
    except Exception:
        # Detection failures should not break import flow.
        pass

    if not decoded_candidates:
        return raw_content.decode("utf-8", errors="ignore")

    return max(decoded_candidates, key=_text_quality_score)


async def import_local_txt(file_name: str, raw_content: bytes) -> dict:
    text = _decode_local_txt(raw_content)

    if not text.strip():
        raise ValueError("TXT file is empty")

    book_name = Path(file_name).stem or "Imported TXT"
    book_url = _make_local_book_url("txt", raw_content)
    source_url = "local://import"
    book_key = build_book_key(source_url, book_url)

    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, category_name, last_chapter, total_chapters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(book_key) DO UPDATE SET
            name = excluded.name,
            book_url = excluded.book_url,
            source_url = excluded.source_url,
            last_chapter = excluded.last_chapter,
            total_chapters = excluded.total_chapters,
            updated_at = excluded.updated_at""",
        (
            book_key,
            book_name,
            "",
            "",
            "Imported from local TXT",
            book_url,
            source_url,
            PUBLISHED_BOOK_CATEGORY_NAME,
            "正文",
            1,
        ),
    )

    book_id = await _get_book_id(db, book_url, source_url)

    await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM chapter_cache WHERE book_id = ?", (book_id,))

    await db.execute(
        "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
        (book_id, "正文", f"{book_url}#1", 0),
    )
    await db.execute(
        """INSERT INTO chapter_cache
        (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
        VALUES (?, ?, ?, ?, ?, 'novel')""",
        (book_id, 0, "正文", f"{book_url}#1", text),
    )
    await db.commit()

    return {"book_id": book_id, "name": book_name}


async def import_local_epub(file_name: str, raw_content: bytes) -> dict:
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise RuntimeError("ebooklib not installed") from exc

    try:
        book = epub.read_epub(io.BytesIO(raw_content))
    except Exception as exc:
        raise ValueError("Invalid EPUB file") from exc

    title = "Imported EPUB"
    title_meta = book.get_metadata("DC", "title")
    if title_meta:
        title = title_meta[0][0] or title
    if file_name:
        title = title or Path(file_name).stem

    author_meta = book.get_metadata("DC", "creator")
    author = author_meta[0][0] if author_meta else ""

    chapters = []
    for item in book.get_items():
        if item.get_type() != 9:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text("\n", strip=True)
        if text.strip():
            chapter_title = _extract_epub_chapter_title(item.get_name(), soup, text)
            chapters.append((chapter_title, text))

    if not chapters:
        raise ValueError("EPUB has no readable chapters")

    book_url = _make_local_book_url("epub", raw_content)
    source_url = "local://import"
    book_key = build_book_key(source_url, book_url)

    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, category_name, last_chapter, total_chapters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(book_key) DO UPDATE SET
            name = excluded.name,
            author = excluded.author,
            book_url = excluded.book_url,
            source_url = excluded.source_url,
            last_chapter = excluded.last_chapter,
            total_chapters = excluded.total_chapters,
            updated_at = excluded.updated_at""",
        (
            book_key,
            title,
            author,
            "",
            "Imported from local EPUB",
            book_url,
            source_url,
            PUBLISHED_BOOK_CATEGORY_NAME,
            chapters[-1][0],
            len(chapters),
        ),
    )

    book_id = await _get_book_id(db, book_url, source_url)

    await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM chapter_cache WHERE book_id = ?", (book_id,))

    for idx, (chapter_title, chapter_text) in enumerate(chapters):
        chapter_url = f"{book_url}#{idx + 1}"
        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, chapter_title, chapter_url, idx),
        )
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'novel')""",
            (book_id, idx, chapter_title, chapter_url, chapter_text),
        )

    await db.commit()
    return {"book_id": book_id, "name": title, "chapters": len(chapters)}


async def delete_books_batch(ids: list[int]) -> int:
    if not ids:
        return 0
    db = await get_db()
    placeholders = ",".join("?" for _ in ids)
    cursor = await db.execute(f"DELETE FROM books WHERE id IN ({placeholders})", ids)
    await db.commit()
    return cursor.rowcount


async def ensure_book_cached(book_id: int) -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = await cursor.fetchone()
    if not book:
        return {"ok": False, "error": "Book not found"}

    cached_count_cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM chapter_cache WHERE book_id = ?",
        (book_id,),
    )
    cached_count = (await cached_count_cursor.fetchone())["cnt"]

    chapters_cursor = await db.execute(
        "SELECT id, title, url, idx FROM chapters WHERE book_id = ? ORDER BY idx ASC",
        (book_id,),
    )
    chapters = await chapters_cursor.fetchall()

    if book["source_url"].startswith("local://"):
        if cached_count == 0:
            return {"ok": False, "error": "Local book cache missing"}
        return {"ok": True, "cached": cached_count, "total": len(chapters) or cached_count}

    if not chapters:
        fetched = await get_chapters(book["book_url"], book["source_url"])
        if not fetched:
            return {"ok": False, "error": "Failed to fetch chapter list"}

        await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
        for chapter in fetched:
            await db.execute(
                "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 0)",
                (book_id, chapter.title, chapter.url, chapter.idx),
            )

        await db.execute(
            "UPDATE books SET total_chapters = ?, last_chapter = ?, updated_at = datetime('now') WHERE id = ?",
            (len(fetched), fetched[-1].title if fetched else "", book_id),
        )
        await db.commit()

        chapters_cursor = await db.execute(
            "SELECT id, title, url, idx FROM chapters WHERE book_id = ? ORDER BY idx ASC",
            (book_id,),
        )
        chapters = await chapters_cursor.fetchall()

    cached_idx_cursor = await db.execute(
        "SELECT chapter_idx FROM chapter_cache WHERE book_id = ?",
        (book_id,),
    )
    cached_idx_rows = await cached_idx_cursor.fetchall()
    cached_idx_set = {int(row["chapter_idx"]) for row in cached_idx_rows}

    missing_chapters = [chapter for chapter in chapters if int(chapter["idx"]) not in cached_idx_set]
    success = len(chapters) - len(missing_chapters)

    async def fetch_missing(chapter_row):
        content = await get_chapter_content(chapter_row["url"], book["source_url"])
        return chapter_row, content

    failed_titles = []
    if missing_chapters:
        concurrency = 6
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_fetch(chapter_row):
            async with semaphore:
                try:
                    return await fetch_missing(chapter_row)
                except Exception:
                    return chapter_row, None

        fetched_results = await asyncio.gather(
            *(bounded_fetch(chapter) for chapter in missing_chapters),
        )

        cache_rows = []
        chapter_ids_to_mark = []
        for chapter_row, content in fetched_results:
            if not content:
                failed_titles.append(chapter_row["title"])
                continue

            cache_rows.append(
                (
                    book_id,
                    chapter_row["idx"],
                    chapter_row["title"],
                    chapter_row["url"],
                    content,
                )
            )
            chapter_ids_to_mark.append((chapter_row["id"],))

        if cache_rows:
            await db.executemany(
                """INSERT OR IGNORE INTO chapter_cache
                (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
                VALUES (?, ?, ?, ?, ?, 'novel')""",
                cache_rows,
            )
        if chapter_ids_to_mark:
            await db.executemany("UPDATE chapters SET cached = 1 WHERE id = ?", chapter_ids_to_mark)

        success += len(cache_rows)

    await db.commit()

    if failed_titles:
        sample = failed_titles[0]
        return {
            "ok": False,
            "error": f"Failed to cache {len(failed_titles)} chapters (e.g. {sample})",
            "cached": success,
            "total": len(chapters),
        }

    return {"ok": True, "cached": success, "total": len(chapters)}


async def get_cache_stats() -> dict:
    db = await get_db()
    total_books_cursor = await db.execute("SELECT COUNT(DISTINCT book_id) AS cnt FROM chapter_cache")
    total_chapters_cursor = await db.execute("SELECT COUNT(*) AS cnt FROM chapter_cache")
    total_bytes_cursor = await db.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) AS total FROM chapter_cache")

    total_books = (await total_books_cursor.fetchone())["cnt"]
    total_chapters = (await total_chapters_cursor.fetchone())["cnt"]
    total_bytes = (await total_bytes_cursor.fetchone())["total"]

    return {
        "books": total_books,
        "chapters": total_chapters,
        "bytes": total_bytes,
    }


async def clear_server_cache(ids: list[int] | None = None) -> int:
    db = await get_db()
    if ids:
        placeholders = ",".join("?" for _ in ids)
        cursor = await db.execute(f"DELETE FROM chapter_cache WHERE book_id IN ({placeholders})", ids)
        await db.execute(f"UPDATE chapters SET cached = 0 WHERE book_id IN ({placeholders})", ids)
        await db.commit()
        return cursor.rowcount

    cursor = await db.execute("DELETE FROM chapter_cache")
    await db.execute("UPDATE chapters SET cached = 0")
    await db.commit()
    return cursor.rowcount
