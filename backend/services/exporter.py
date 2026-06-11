import html
from pathlib import Path

from backend.config import settings
from backend.database import get_db
from backend.services.book_manager import ensure_book_cached


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", " ")).strip()
    return (cleaned or "book").replace(" ", "_")


async def export_book(book_id: int, fmt: str) -> dict:
    if fmt not in ("txt", "epub"):
        raise ValueError("Unsupported export format")

    cache_result = await ensure_book_cached(book_id)
    if not cache_result.get("ok"):
        return {
            "ok": False,
            "book_id": book_id,
            "error": cache_result.get("error", "Failed to cache book before export"),
        }

    db = await get_db()
    cursor = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = await cursor.fetchone()
    if not book:
        return {"ok": False, "book_id": book_id, "error": "Book not found"}

    chapters_cursor = await db.execute(
        """SELECT chapter_idx, chapter_title, content
        FROM chapter_cache
        WHERE book_id = ?
        ORDER BY chapter_idx ASC""",
        (book_id,),
    )
    chapters = await chapters_cursor.fetchall()
    if not chapters:
        return {"ok": False, "book_id": book_id, "error": "No cached chapters found"}

    settings.export_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "txt":
        file_name = f"{_safe_filename(book['name'])}-{book_id}.txt"
        file_path = settings.export_dir / file_name
        _write_txt(file_path, book, chapters)
    else:
        file_name = f"{_safe_filename(book['name'])}-{book_id}.epub"
        file_path = settings.export_dir / file_name
        _write_epub(file_path, book, chapters)

    return {
        "ok": True,
        "book_id": book_id,
        "name": book["name"],
        "format": fmt,
        "file_name": file_name,
        "download_url": f"/api/books/exports/{file_name}",
    }


def _write_txt(path: Path, book, chapters) -> None:
    lines = [book["name"], f"作者: {book['author'] or '未知'}", ""]
    if book["intro"]:
        lines.append(book["intro"])
        lines.append("")

    for chapter in chapters:
        lines.append(f"\n{chapter['chapter_title']}\n")
        lines.append(chapter["content"])
        lines.append("\n")

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_epub(path: Path, book, chapters) -> None:
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise RuntimeError("ebooklib not installed") from exc

    epub_book = epub.EpubBook()
    epub_book.set_identifier(f"easyreader-{book['id']}")
    epub_book.set_title(book["name"])
    epub_book.set_language("zh")
    epub_book.add_author(book["author"] or "未知")

    epub_items = []
    for chapter in chapters:
        chapter_title = chapter["chapter_title"] or f"第{chapter['chapter_idx'] + 1}章"
        body = html.escape(chapter["content"] or "").replace("\n", "<br/>")
        item = epub.EpubHtml(
            title=chapter_title,
            file_name=f"chap_{chapter['chapter_idx'] + 1}.xhtml",
            lang="zh",
        )
        item.content = f"<h1>{html.escape(chapter_title)}</h1><p>{body}</p>"
        epub_book.add_item(item)
        epub_items.append(item)

    epub_book.toc = tuple(epub_items)
    epub_book.spine = ["nav", *epub_items]
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())

    epub.write_epub(str(path), epub_book)
