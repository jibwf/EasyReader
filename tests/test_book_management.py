import pytest

from backend.config import settings
from backend.database import close_db
from backend.database import get_db
from backend.services.book_manager import import_local_epub
from backend.services.book_manager import import_local_txt
from backend.services.content import get_book_info, get_chapters, get_chapter_content
from backend.services.exporter import export_book
from backend.utils.book_key import build_book_key


def _build_epub_bytes(tmp_path, chapters: list[tuple[str, str]]) -> bytes:
    epub = pytest.importorskip("ebooklib.epub")

    book = epub.EpubBook()
    book.set_identifier("test-epub")
    book.set_title("测试 EPUB")
    book.set_language("zh-CN")

    spine = ["nav"]
    chapter_items = []
    for idx, (file_name, html) in enumerate(chapters, start=1):
        chapter = epub.EpubHtml(title="", file_name=file_name, lang="zh-CN")
        chapter.set_content(html)
        book.add_item(chapter)
        chapter_items.append(chapter)
        spine.append(chapter)

    book.toc = tuple(chapter_items)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub_path = tmp_path / "sample.epub"
    epub.write_epub(str(epub_path), book)
    return epub_path.read_bytes()


@pytest.mark.asyncio
async def test_local_txt_import_can_be_read_via_content_service(tmp_path, monkeypatch):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    imported = await import_local_txt("sample.txt", "第一章\n这是正文".encode("utf-8"))
    assert imported["book_id"] > 0

    db = await get_db()
    cursor = await db.execute("SELECT * FROM books WHERE id = ?", (imported["book_id"],))
    row = await cursor.fetchone()
    assert row["category_name"] == "出版"

    info = await get_book_info(row["book_url"], row["source_url"])
    assert info is not None
    assert info.name == "sample"

    chapters = await get_chapters(row["book_url"], row["source_url"])
    assert len(chapters) == 1

    content = await get_chapter_content(chapters[0].url, row["source_url"])
    assert "这是正文" in content


@pytest.mark.asyncio
async def test_local_txt_import_supports_gb18030_encoding(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    gb18030_text = "第一章\n这是GB18030编码正文，中文不应乱码。"
    imported = await import_local_txt("gb18030.txt", gb18030_text.encode("gb18030"))
    assert imported["book_id"] > 0

    db = await get_db()
    cursor = await db.execute("SELECT * FROM books WHERE id = ?", (imported["book_id"],))
    row = await cursor.fetchone()

    chapters = await get_chapters(row["book_url"], row["source_url"])
    assert len(chapters) == 1

    content = await get_chapter_content(chapters[0].url, row["source_url"])
    assert "GB18030编码正文" in content
    assert "乱码" in content


@pytest.mark.asyncio
async def test_local_txt_import_splits_multiple_chapters(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    raw_text = "\n".join(
        [
            "第一章 起风了",
            "这是第一章正文。",
            "",
            "第二章 雨将至",
            "这是第二章正文。",
        ]
    )
    imported = await import_local_txt("multi.txt", raw_text.encode("utf-8"))
    assert imported["book_id"] > 0
    assert imported["chapters"] == 2

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, book_url, source_url, total_chapters, last_chapter FROM books WHERE id = ?",
        (imported["book_id"],),
    )
    row = await cursor.fetchone()
    assert row["total_chapters"] == 2
    assert row["last_chapter"] == "第二章 雨将至"

    chapters = await get_chapters(row["book_url"], row["source_url"])
    assert [chapter.title for chapter in chapters] == ["第一章 起风了", "第二章 雨将至"]

    first_content = await get_chapter_content(chapters[0].url, row["source_url"])
    second_content = await get_chapter_content(chapters[1].url, row["source_url"])
    assert "第一章正文" in first_content
    assert "第二章正文" in second_content


@pytest.mark.asyncio
async def test_local_txt_import_supports_parenthesized_chapter_titles(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    raw_text = "\n".join(
        [
            "（1）初战",
            "这是初战正文。",
            "",
            "（三）",
            "这是第三部分正文。",
        ]
    )
    imported = await import_local_txt("paren.txt", raw_text.encode("utf-8"))
    assert imported["book_id"] > 0
    assert imported["chapters"] == 2

    db = await get_db()
    cursor = await db.execute(
        "SELECT book_url, source_url, total_chapters FROM books WHERE id = ?",
        (imported["book_id"],),
    )
    row = await cursor.fetchone()
    assert row["total_chapters"] == 2

    chapters = await get_chapters(row["book_url"], row["source_url"])
    assert [chapter.title for chapter in chapters] == ["（1）初战", "（三）"]

    first_content = await get_chapter_content(chapters[0].url, row["source_url"])
    second_content = await get_chapter_content(chapters[1].url, row["source_url"])
    assert "初战正文" in first_content
    assert "第三部分正文" in second_content


@pytest.mark.asyncio
async def test_reimporting_same_txt_keeps_single_chapter(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    await import_local_txt("sample.txt", "第一章\n这是正文".encode("utf-8"))
    await import_local_txt("sample.txt", "第一章\n这是正文".encode("utf-8"))

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, book_url, source_url FROM books WHERE book_url LIKE 'local://txt/%'"
    )
    row = await cursor.fetchone()

    chapter_cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM chapters WHERE book_id = ?",
        (row["id"],),
    )
    chapter_count = (await chapter_cursor.fetchone())["cnt"]
    assert chapter_count == 1

    chapters = await get_chapters(row["book_url"], row["source_url"])
    assert len(chapters) == 1


@pytest.mark.asyncio
async def test_import_local_epub_prefers_visible_heading_for_chapter_title(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    raw_epub = _build_epub_bytes(
        tmp_path,
        [
            (
                "Text/chapter_01.xhtml",
                "<html><body><h1>第一章 起风了</h1><p>这是正文。</p></body></html>",
            )
        ],
    )

    imported = await import_local_epub("sample.epub", raw_epub)

    db = await get_db()
    book_cursor = await db.execute("SELECT category_name FROM books WHERE id = ?", (imported["book_id"],))
    book_row = await book_cursor.fetchone()
    assert book_row["category_name"] == "出版"

    cursor = await db.execute(
        "SELECT title FROM chapters WHERE book_id = ? ORDER BY idx ASC",
        (imported["book_id"],),
    )
    row = await cursor.fetchone()
    assert row["title"] == "第一章 起风了"


@pytest.mark.asyncio
async def test_import_local_epub_cleans_path_like_chapter_title(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    raw_epub = _build_epub_bytes(
        tmp_path,
        [
            (
                "Text/chapter_02.xhtml",
                "<html><body><p>Chapter 02 opening line</p><p>More text.</p></body></html>",
            )
        ],
    )

    imported = await import_local_epub("sample.epub", raw_epub)

    db = await get_db()
    cursor = await db.execute(
        "SELECT title FROM chapters WHERE book_id = ? ORDER BY idx ASC",
        (imported["book_id"],),
    )
    row = await cursor.fetchone()
    assert row["title"] == "Chapter 02 opening line"


@pytest.mark.asyncio
async def test_export_book_requires_cache_then_generates_txt(tmp_path, monkeypatch):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    db = await get_db()
    source_url = "https://source.example"
    book_url = "https://book.example/1"
    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (build_book_key(source_url, book_url), "导出测试", "作者", "", "", book_url, source_url, 1),
    )
    cursor = await db.execute("SELECT id FROM books WHERE book_url = ?", (book_url,))
    book_id = (await cursor.fetchone())["id"]
    await db.execute(
        "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 0)",
        (book_id, "第一章", "https://book.example/1/ch1", 0),
    )
    await db.commit()

    async def fake_get_chapter_content(chapter_url: str, source_url: str) -> str:
        return "缓存后的章节正文"

    monkeypatch.setattr("backend.services.book_manager.get_chapter_content", fake_get_chapter_content)

    result = await export_book(book_id, "txt")
    assert result["ok"] is True
    assert result["download_url"].endswith(".txt")
