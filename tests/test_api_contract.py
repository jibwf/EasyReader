import asyncio
import time

from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import close_db, get_db
from backend.main import API_CONTRACT_VERSION, SUPPORTED_CLIENT_TYPES, app
from backend.utils.book_key import build_book_key


def _setup_tmp_data(tmp_path):
    asyncio.run(close_db())
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"


def _seed_contract_book() -> int:
    async def _inner() -> int:
        db = await get_db()
        source_url = "local://import"
        book_url = "local://txt/contract-book"
        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, category_name, last_chapter, total_chapters, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                build_book_key(source_url, book_url),
                "Contract Book",
                "Contract Author",
                "",
                "Intro",
                book_url,
                source_url,
                "网文",
                "Chapter 1",
                1,
            ),
        )
        cursor = await db.execute(
            "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
            (book_url, source_url),
        )
        row = await cursor.fetchone()
        book_id = row["id"]
        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, "Chapter 1", "local://txt/contract-book#1", 0),
        )
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'novel')""",
            (book_id, 0, "Chapter 1", "local://txt/contract-book#1", "Contract chapter content"),
        )
        await db.commit()
        return book_id

    return asyncio.run(_inner())


def _wait_for_offline_task(client: TestClient, task_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    latest: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/offline/tasks/{task_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)

    assert latest is not None
    return latest


def _assert_contract_headers(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-server-version"]
    assert response.headers["x-api-contract-version"] == API_CONTRACT_VERSION
    supported_types = response.headers["x-supported-client-types"].split(",")
    assert supported_types == SUPPORTED_CLIENT_TYPES


def test_version_endpoint_freezes_contract_metadata_and_headers(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        response = client.get(
            "/api/version",
            headers={
                "X-Client-Type": "web-pwa",
                "X-Client-Version": "contract-test",
                "X-API-Contract-Version": API_CONTRACT_VERSION,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert body["api_contract_version"] == API_CONTRACT_VERSION
    assert body["supported_client_types"] == SUPPORTED_CLIENT_TYPES
    _assert_contract_headers(response)


def test_books_and_content_contract_fields(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_contract_book()
    contract_book_key = build_book_key("local://import", "local://txt/contract-book")

    with TestClient(app) as client:
        books_response = client.get("/api/books")
        chapters_response = client.get(
            "/api/content/chapters",
            params={"book_key": contract_book_key},
        )
        chapter_response = client.get(
            "/api/content/chapter",
            params={"url": "local://txt/contract-book#1", "source_url": "local://import"},
        )

    assert books_response.status_code == 200
    _assert_contract_headers(books_response)
    book = books_response.json()[0]
    assert {
        "id",
        "book_key",
        "name",
        "author",
        "cover_url",
        "intro",
        "book_url",
        "source_url",
        "category_name",
        "last_chapter",
        "total_chapters",
        "added_at",
        "updated_at",
    }.issubset(book.keys())
    assert book["id"] == book_id
    assert book["book_url"] == "local://txt/contract-book"
    assert book["source_url"] == "local://import"

    assert chapters_response.status_code == 200
    _assert_contract_headers(chapters_response)
    chapter = chapters_response.json()[0]
    assert {"id", "book_id", "title", "url", "idx", "cached"}.issubset(chapter.keys())
    assert chapter["book_id"] == book_id
    assert chapter["cached"] is True

    assert chapter_response.status_code == 200
    _assert_contract_headers(chapter_response)
    assert chapter_response.json() == {
        "type": "novel",
        "content": "Contract chapter content",
        "images": [],
    }


def test_sync_progress_contract_fields_and_cursor(tmp_path):
    _setup_tmp_data(tmp_path)

    payload = {
        "user_id": "contract-user",
        "device_id": "eink-01",
        "book_key": build_book_key("local://import", "local://txt/contract-book"),
        "book_url": "local://txt/contract-book",
        "source_url": "local://import",
        "book_name": "Contract Book",
        "chapter_idx": 3,
        "chapter_title": "Chapter 3",
        "chapter_url": "local://txt/contract-book#3",
        "position": 0.42,
    }

    with TestClient(app) as client:
        upsert_response = client.post("/api/sync/progress/upsert", json=payload)
        pull_response = client.get(
            "/api/sync/progress/pull",
            params={"user_id": "contract-user", "since": 0, "limit": 100},
        )

    assert upsert_response.status_code == 200
    _assert_contract_headers(upsert_response)
    item = upsert_response.json()
    assert {
        "user_id",
        "device_id",
        "book_key",
        "book_url",
        "source_url",
        "book_name",
        "chapter_idx",
        "chapter_title",
        "chapter_url",
        "position",
        "revision",
        "updated_at",
        "accepted",
        "conflict",
        "conflict_reason",
    }.issubset(item.keys())
    assert item["accepted"] is True
    assert item["conflict"] is False

    assert pull_response.status_code == 200
    _assert_contract_headers(pull_response)
    pulled = pull_response.json()
    assert len(pulled["items"]) == 1
    assert pulled["items"][0]["revision"] == item["revision"]
    assert pulled["next_cursor"] == item["revision"]


def test_offline_and_fonts_contract_smoke(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_contract_book()
    font_path = settings.font_dir / "ContractFont.ttf"
    font_path.parent.mkdir(parents=True, exist_ok=True)
    font_path.write_bytes(b"contract-font")

    with TestClient(app) as client:
        task_response = client.post(
            "/api/offline/tasks",
            json={"user_id": "contract-user", "device_id": "eink-01", "book_id": book_id},
        )
        fonts_response = client.get("/api/fonts")

        assert task_response.status_code == 200
        _assert_contract_headers(task_response)
        created_task = task_response.json()
        assert {
            "task_id",
            "user_id",
            "device_id",
            "book_id",
            "book_key",
            "book_name",
            "book_url",
            "source_url",
            "status",
            "progress",
            "total_chapters",
            "cached_chapters",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
        }.issubset(created_task.keys())
        assert created_task["status"] in {"queued", "running", "completed"}
        assert 0 <= created_task["progress"] <= 100

        task = _wait_for_offline_task(client, created_task["task_id"])
        assert task["status"] == "completed"
        assert task["cached_chapters"] == 1

        catalog_response = client.get(
            "/api/offline/catalog",
            params={"user_id": "contract-user", "device_id": "eink-01"},
        )
        assert catalog_response.status_code == 200
        _assert_contract_headers(catalog_response)
        catalog_item = catalog_response.json()[0]
        assert {
            "user_id",
            "device_id",
            "book_id",
            "book_key",
            "book_url",
            "source_url",
            "name",
            "author",
            "total_chapters",
            "cached_chapters",
            "updated_at",
        }.issubset(catalog_item.keys())
        assert catalog_item["book_id"] == book_id

        assert fonts_response.status_code == 200
        _assert_contract_headers(fonts_response)
        font = fonts_response.json()[0]
        assert {
            "id",
            "name",
            "file_name",
            "extension",
            "size_bytes",
            "sha256",
            "download_url",
        }.issubset(font.keys())
        assert font["file_name"] == "ContractFont.ttf"
        assert font["download_url"] == "/api/fonts/ContractFont.ttf/download"