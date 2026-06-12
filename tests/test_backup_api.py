import asyncio
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import close_db, get_db
from backend.main import app
from backend.utils.book_key import build_book_key


def _setup_tmp_data(tmp_path):
    asyncio.run(close_db())
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"


def _seed_backup_fixture(chapter_idx: int = 2, revision: int = 1):
    async def _inner():
        db = await get_db()
        source_url = "local://import"
        book_url = "local://txt/backup-test"
        book_key = build_book_key(source_url, book_url)

        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (book_key, "备份测试书", "作者", "", "", book_url, source_url, 1),
        )

        cursor = await db.execute(
            "SELECT id FROM books WHERE book_key = ?",
            (book_key,),
        )
        book_id = (await cursor.fetchone())["id"]

        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, "第一章", f"{book_url}#1", 0),
        )
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'novel')""",
            (book_id, 0, "第一章", f"{book_url}#1", "章节内容"),
        )
        await db.execute(
            """INSERT INTO sync_progress
            (user_id, book_key, book_url, source_url, book_name, chapter_idx, chapter_title,
             chapter_url, position, device_id, updated_at, revision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
            (
                "u1",
                book_key,
                book_url,
                source_url,
                "备份测试书",
                chapter_idx,
                f"第{chapter_idx}章",
                f"{book_url}#{chapter_idx}",
                0.5,
                "web-01",
                revision,
            ),
        )

        await db.commit()
        return book_key

    return asyncio.run(_inner())


def _count_books() -> int:
    async def _inner() -> int:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM books")
        return int((await cursor.fetchone())["cnt"])

    return asyncio.run(_inner())


def _get_sync_chapter_idx(book_key: str) -> int:
    async def _inner() -> int:
        db = await get_db()
        cursor = await db.execute(
            "SELECT chapter_idx FROM sync_progress WHERE user_id = ? AND book_key = ?",
            ("u1", book_key),
        )
        row = await cursor.fetchone()
        return int(row["chapter_idx"])

    return asyncio.run(_inner())


def _set_sync_progress(book_key: str, chapter_idx: int, revision: int):
    async def _inner():
        db = await get_db()
        await db.execute(
            """UPDATE sync_progress
            SET chapter_idx = ?, chapter_title = ?, chapter_url = ?, revision = ?, updated_at = datetime('now')
            WHERE user_id = ? AND book_key = ?""",
            (chapter_idx, f"第{chapter_idx}章", f"local://txt/backup-test#{chapter_idx}", revision, "u1", book_key),
        )
        await db.commit()

    asyncio.run(_inner())


def _add_extra_book():
    async def _inner():
        db = await get_db()
        source_url = "local://import"
        book_url = "local://txt/extra"
        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (build_book_key(source_url, book_url), "额外书籍", "作者", "", "", book_url, source_url, 1),
        )
        await db.commit()

    asyncio.run(_inner())


def test_backup_export_and_full_restore(tmp_path):
    _setup_tmp_data(tmp_path)
    book_key = _seed_backup_fixture(chapter_idx=2, revision=1)

    settings.font_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    original_font = b"font-v1"
    original_export = b"export-v1"
    (settings.font_dir / "reader.ttf").write_bytes(original_font)
    (settings.export_dir / "book.txt").write_bytes(original_export)

    with TestClient(app) as client:
        export_resp = client.get("/api/backup/export")
        assert export_resp.status_code == 200
        assert export_resp.headers["content-type"].startswith("application/zip")
        backup_blob = export_resp.content

        with ZipFile(BytesIO(backup_blob), "r") as archive:
            names = set(archive.namelist())
            assert "snapshot.json" in names
            assert "manifest.json" in names

        _add_extra_book()
        _set_sync_progress(book_key, chapter_idx=9, revision=9)
        (settings.font_dir / "reader.ttf").write_bytes(b"font-v2")
        (settings.export_dir / "book.txt").write_bytes(b"export-v2")

        restore_resp = client.post(
            "/api/backup/restore?mode=full&conflict_policy=backup_wins",
            files={"file": ("backup.zip", BytesIO(backup_blob), "application/zip")},
        )
        assert restore_resp.status_code == 200
        body = restore_resp.json()
        assert body["ok"] is True
        assert body["mode"] == "full"

    assert _count_books() == 1
    assert _get_sync_chapter_idx(book_key) == 2
    assert (settings.font_dir / "reader.ttf").read_bytes() == original_font
    assert (settings.export_dir / "book.txt").read_bytes() == original_export


def test_backup_incremental_restore_local_wins_on_conflict(tmp_path):
    _setup_tmp_data(tmp_path)
    book_key = _seed_backup_fixture(chapter_idx=3, revision=3)

    with TestClient(app) as client:
        export_resp = client.get("/api/backup/export")
        assert export_resp.status_code == 200
        backup_blob = export_resp.content

        _set_sync_progress(book_key, chapter_idx=12, revision=12)

        restore_resp = client.post(
            "/api/backup/restore?mode=incremental&conflict_policy=local_wins",
            files={"file": ("backup.zip", BytesIO(backup_blob), "application/zip")},
        )
        assert restore_resp.status_code == 200
        body = restore_resp.json()
        assert body["ok"] is True
        assert body["mode"] == "incremental"
        assert body["conflicts"] >= 1
        assert body["tables"]["sync_progress"]["resolved_with_local"] >= 1

    assert _get_sync_chapter_idx(book_key) == 12