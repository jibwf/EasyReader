import asyncio
import json
from io import BytesIO
from urllib.parse import quote

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


def _seed_local_book() -> int:
    async def _inner() -> int:
        db = await get_db()
        source_url = "local://import"
        book_url = "local://txt/test-book"
        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (build_book_key(source_url, book_url), "本地测试书", "作者", "", "", book_url, source_url, 1),
        )
        cursor = await db.execute(
            "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
            (book_url, source_url),
        )
        row = await cursor.fetchone()
        book_id = row["id"]
        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, "第一章", "local://txt/test-book#1", 0),
        )
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'novel')""",
            (book_id, 0, "第一章", "local://txt/test-book#1", "章节正文"),
        )
        await db.commit()
        return book_id

    return asyncio.run(_inner())


def test_api_batch_import_json(tmp_path):
    _setup_tmp_data(tmp_path)

    payload = [
        {
            "name": "导入书A",
            "author": "A",
            "cover_url": "",
            "intro": "",
            "book_url": "https://book.example/a",
            "source_url": "https://source.example",
        },
        {
            "name": "导入书B",
            "author": "B",
            "cover_url": "",
            "intro": "",
            "book_url": "https://book.example/b",
            "source_url": "https://source.example",
        },
    ]

    with TestClient(app) as client:
        response = client.post(
            "/api/books/import",
            files={
                "file": (
                    "books.json",
                    BytesIO(json.dumps(payload).encode("utf-8")),
                    "application/json",
                )
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["imported"] == 2
        assert body["failed"] == 0

        books_resp = client.get("/api/books")
        assert books_resp.status_code == 200
        assert len(books_resp.json()) == 2


def test_api_batch_export_txt_and_download(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    with TestClient(app) as client:
        response = client.post(
            "/api/books/export-batch",
            json={"ids": [book_id], "format": "txt"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] == 1
        assert body["results"][0]["ok"] is True

        download_url = body["results"][0]["download_url"]
        file_response = client.get(download_url)
        assert file_response.status_code == 200
        assert "章节正文" in file_response.text


def test_api_clear_cache_by_ids(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    with TestClient(app) as client:
        stats_before = client.get("/api/books/cache/stats")
        assert stats_before.status_code == 200
        assert stats_before.json()["chapters"] == 1

        clear_resp = client.post(
            "/api/books/cache/clear",
            json={"ids": [book_id], "clear_all": False},
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["cleared"] == 1

        stats_after = client.get("/api/books/cache/stats")
        assert stats_after.status_code == 200
        assert stats_after.json()["chapters"] == 0


def test_api_clear_cache_all(tmp_path):
    _setup_tmp_data(tmp_path)
    _seed_local_book()

    with TestClient(app) as client:
        stats_before = client.get("/api/books/cache/stats")
        assert stats_before.status_code == 200
        assert stats_before.json()["chapters"] == 1

        clear_resp = client.post(
            "/api/books/cache/clear",
            json={"clear_all": True},
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["clear_all"] is True
        assert clear_resp.json()["cleared"] == 1

        stats_after = client.get("/api/books/cache/stats")
        assert stats_after.status_code == 200
        assert stats_after.json()["chapters"] == 0


def test_api_cache_batch_returns_friendly_error_on_failure(tmp_path, monkeypatch):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    async def fake_ensure_book_cached(book_id_value: int):
        raise RuntimeError("数据库约束冲突")

    monkeypatch.setattr("backend.routers.books.ensure_book_cached", fake_ensure_book_cached)

    with TestClient(app) as client:
        response = client.post(
            "/api/books/cache-batch",
            json={"ids": [book_id]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] == 0
        assert body["results"][0]["ok"] is False
        assert "缓存失败" in body["results"][0]["error"]


def test_api_categories_hide_and_visibility_filter(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        add_web = client.post(
            "/api/books",
            json={
                "name": "网文书",
                "book_url": "https://book.example/web-1",
                "source_url": "https://source.example/main",
                "category_name": "网文",
            },
        )
        assert add_web.status_code == 200

        add_pub = client.post(
            "/api/books",
            json={
                "name": "出版书",
                "book_url": "https://book.example/pub-1",
                "source_url": "https://source.example/main",
            },
        )
        assert add_pub.status_code == 200

        books_resp = client.get("/api/books")
        assert books_resp.status_code == 200
        books = books_resp.json()
        pub_id = next(item["id"] for item in books if item["name"] == "出版书")

        assign_resp = client.put(
            f"/api/books/{pub_id}/category",
            json={"category_name": "出版"},
        )
        assert assign_resp.status_code == 200

        categories_resp = client.get("/api/books/categories")
        assert categories_resp.status_code == 200
        names = {item["name"] for item in categories_resp.json()}
        assert "网文" in names
        assert "出版" in names

        hide_resp = client.put(
            f"/api/books/categories/{quote('出版')}/hidden",
            json={"hidden": True},
        )
        assert hide_resp.status_code == 200
        assert hide_resp.json()["hidden"] is True

        visible_books_resp = client.get("/api/books")
        assert visible_books_resp.status_code == 200
        visible_books = visible_books_resp.json()
        assert len(visible_books) == 1
        assert visible_books[0]["name"] == "网文书"

        all_books_resp = client.get("/api/books?include_hidden=true")
        assert all_books_resp.status_code == 200
        assert len(all_books_resp.json()) == 2


def test_api_source_add_defaults_to_web_novel_category(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/books",
            json={
                "name": "来源书籍",
                "book_url": "https://book.example/source-1",
                "source_url": "https://source.example/novel",
                "category_name": "出版",
            },
        )
        assert response.status_code == 200

        books_resp = client.get("/api/books")
        assert books_resp.status_code == 200
        books = books_resp.json()
        assert len(books) == 1
        assert books[0]["category_name"] == "网文"


def test_api_categories_create_and_batch_assign(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        first_add = client.post(
            "/api/books",
            json={
                "name": "书A",
                "book_url": "https://book.example/a-1",
                "source_url": "https://source.example/a",
            },
        )
        second_add = client.post(
            "/api/books",
            json={
                "name": "书B",
                "book_url": "https://book.example/b-1",
                "source_url": "https://source.example/b",
            },
        )
        assert first_add.status_code == 200
        assert second_add.status_code == 200

        books_resp = client.get("/api/books")
        assert books_resp.status_code == 200
        book_ids = [item["id"] for item in books_resp.json()]
        assert len(book_ids) == 2

        create_category_resp = client.post(
            "/api/books/categories",
            json={"name": "科幻"},
        )
        assert create_category_resp.status_code == 200
        assert create_category_resp.json()["name"] == "科幻"

        batch_assign_resp = client.post(
            "/api/books/category-batch",
            json={"ids": book_ids, "category_name": "科幻"},
        )
        assert batch_assign_resp.status_code == 200
        body = batch_assign_resp.json()
        assert body["updated"] == 2
        assert body["requested"] == 2
        assert body["category_name"] == "科幻"

        sci_fi_books = client.get(f"/api/books?category={quote('科幻')}")
        assert sci_fi_books.status_code == 200
        data = sci_fi_books.json()
        assert len(data) == 2
        assert {item["category_name"] for item in data} == {"科幻"}


def test_api_categories_rename_and_delete_without_deleting_books(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        first_add = client.post(
            "/api/books",
            json={
                "name": "重命名测试A",
                "book_url": "https://book.example/rn-a",
                "source_url": "https://source.example/a",
            },
        )
        second_add = client.post(
            "/api/books",
            json={
                "name": "重命名测试B",
                "book_url": "https://book.example/rn-b",
                "source_url": "https://source.example/b",
            },
        )
        assert first_add.status_code == 200
        assert second_add.status_code == 200

        books_resp = client.get("/api/books")
        assert books_resp.status_code == 200
        book_ids = [item["id"] for item in books_resp.json()]

        create_category_resp = client.post(
            "/api/books/categories",
            json={"name": "科幻"},
        )
        assert create_category_resp.status_code == 200

        assign_resp = client.post(
            "/api/books/category-batch",
            json={"ids": book_ids, "category_name": "科幻"},
        )
        assert assign_resp.status_code == 200

        rename_resp = client.put(
            f"/api/books/categories/{quote('科幻')}/rename",
            json={"new_name": "科幻文学"},
        )
        assert rename_resp.status_code == 200
        assert rename_resp.json()["new_name"] == "科幻文学"

        renamed_books_resp = client.get(f"/api/books?category={quote('科幻文学')}")
        assert renamed_books_resp.status_code == 200
        renamed_books = renamed_books_resp.json()
        assert len(renamed_books) == 2
        assert {item["category_name"] for item in renamed_books} == {"科幻文学"}

        delete_resp = client.delete(f"/api/books/categories/{quote('科幻文学')}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True
        assert delete_resp.json()["reassigned_to"] == "网文"

        all_books_resp = client.get("/api/books")
        assert all_books_resp.status_code == 200
        all_books = all_books_resp.json()
        assert len(all_books) == 2
        assert {item["category_name"] for item in all_books} == {"网文"}
