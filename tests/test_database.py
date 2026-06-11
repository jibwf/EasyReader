import aiosqlite
import pytest

from backend.database import SCHEMA, _ensure_default_book_categories


@pytest.mark.asyncio
async def test_schema_contains_source_format_and_book_key_columns():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)

    source_cursor = await db.execute("PRAGMA table_info(book_sources)")
    source_columns = {row["name"] for row in await source_cursor.fetchall()}

    book_cursor = await db.execute("PRAGMA table_info(books)")
    book_columns = {row["name"] for row in await book_cursor.fetchall()}

    await db.close()

    assert "source_format" in source_columns
    assert "book_key" in book_columns


@pytest.mark.asyncio
async def test_chapters_unique_constraint_enforced_by_schema():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)

    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
        VALUES ('bk_test', '书名', '作者', '', '', 'local://book', 'local://source', 1, datetime('now'))"""
    )
    row_cursor = await db.execute("SELECT id FROM books WHERE book_key = 'bk_test'")
    row = await row_cursor.fetchone()
    book_id = row["id"]

    await db.execute(
        "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
        (book_id, "正文", "local://chapter/1", 0),
    )

    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, "正文重复", "local://chapter/1-dup", 0),
        )

    await db.close()


@pytest.mark.asyncio
async def test_default_book_categories_seeded_and_marked_preset():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)

    await _ensure_default_book_categories(db)
    await db.commit()

    cursor = await db.execute("SELECT name, preset, hidden FROM book_categories")
    rows = await cursor.fetchall()
    await db.close()

    category_map = {row["name"]: (row["preset"], row["hidden"]) for row in rows}
    assert category_map["网文"] == (1, 0)
    assert category_map["出版"] == (1, 0)
