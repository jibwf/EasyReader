import asyncio
import time

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
        book_url = "local://txt/test-offline"
        await db.execute(
            """INSERT INTO books
            (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (build_book_key(source_url, book_url), "Offline Test Book", "Author", "", "", book_url, source_url, 1),
        )
        cursor = await db.execute(
            "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
            (book_url, source_url),
        )
        row = await cursor.fetchone()
        book_id = row["id"]
        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, "Chapter 1", "local://txt/test-offline#1", 0),
        )
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'novel')""",
            (book_id, 0, "Chapter 1", "local://txt/test-offline#1", "cached content"),
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


def test_sync_progress_upsert_and_pull(tmp_path):
    _setup_tmp_data(tmp_path)
    book_key = build_book_key("https://source.example", "https://book.example/1")

    with TestClient(app) as client:
        upsert_resp = client.post(
            "/api/sync/progress/upsert",
            json={
                "user_id": "u1",
                "device_id": "android-01",
                "book_key": book_key,
                "book_url": "https://book.example/1",
                "source_url": "https://source.example",
                "book_name": "Book 1",
                "chapter_idx": 12,
                "chapter_title": "Chapter 12",
                "chapter_url": "https://book.example/1/12",
                "position": 34.5,
            },
        )
        assert upsert_resp.status_code == 200
        upsert_body = upsert_resp.json()
        assert upsert_body["revision"] >= 1
        assert upsert_body["book_name"] == "Book 1"
        assert upsert_body["book_key"] == book_key

        pull_resp = client.get("/api/sync/progress/pull", params={"user_id": "u1", "since": 0})
        assert pull_resp.status_code == 200
        pull_body = pull_resp.json()
        assert len(pull_body["items"]) == 1
        assert pull_body["items"][0]["chapter_idx"] == 12
        assert pull_body["next_cursor"] == pull_body["items"][0]["revision"]


def test_api_version_exposes_contract_metadata(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        resp = client.get("/api/version")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"]
        assert body["api_contract_version"] == "2026-06-11"
        assert "web-pwa" in body["supported_client_types"]
        assert "eink-android" in body["supported_client_types"]
        assert resp.headers["x-api-contract-version"] == "2026-06-11"
        assert "web-pwa" in resp.headers["x-supported-client-types"]


def test_sync_progress_rejects_large_regression(tmp_path):
    _setup_tmp_data(tmp_path)
    book_key = build_book_key("https://source.example", "https://book.example/1")

    with TestClient(app) as client:
        first_resp = client.post(
            "/api/sync/progress/upsert",
            json={
                "user_id": "u1",
                "device_id": "android-01",
                "book_key": book_key,
                "book_url": "https://book.example/1",
                "source_url": "https://source.example",
                "book_name": "Book 1",
                "chapter_idx": 10,
                "chapter_title": "Chapter 10",
                "chapter_url": "https://book.example/1/10",
                "position": 0.78,
            },
        )
        assert first_resp.status_code == 200
        first_body = first_resp.json()
        assert first_body["accepted"] is True

        stale_resp = client.post(
            "/api/sync/progress/upsert",
            json={
                "user_id": "u1",
                "device_id": "android-02",
                "book_key": book_key,
                "book_url": "https://book.example/1",
                "source_url": "https://source.example",
                "book_name": "Book 1",
                "chapter_idx": 10,
                "chapter_title": "Chapter 10",
                "chapter_url": "https://book.example/1/10",
                "position": 0.4,
            },
        )
        assert stale_resp.status_code == 200
        stale_body = stale_resp.json()
        assert stale_body["accepted"] is False
        assert stale_body["conflict"] is True
        assert stale_body["conflict_reason"] == "position_regression"
        assert stale_body["revision"] == first_body["revision"]
        assert stale_body["position"] == first_body["position"]

        pull_resp = client.get("/api/sync/progress/pull", params={"user_id": "u1", "since": 0})
        assert pull_resp.status_code == 200
        pull_body = pull_resp.json()
        assert len(pull_body["items"]) == 1
        assert pull_body["items"][0]["position"] == first_body["position"]

        force_resp = client.post(
            "/api/sync/progress/upsert",
            json={
                "user_id": "u1",
                "device_id": "android-02",
                "book_key": book_key,
                "book_url": "https://book.example/1",
                "source_url": "https://source.example",
                "book_name": "Book 1",
                "chapter_idx": 10,
                "chapter_title": "Chapter 10",
                "chapter_url": "https://book.example/1/10",
                "position": 0.4,
                "force": True,
            },
        )
        assert force_resp.status_code == 200
        force_body = force_resp.json()
        assert force_body["accepted"] is True
        assert force_body["conflict"] is False
        assert force_body["position"] == 0.4


def test_sync_bookmarks_batch_and_pull(tmp_path):
    _setup_tmp_data(tmp_path)
    book_key = build_book_key("https://source.example", "https://book.example/1")

    with TestClient(app) as client:
        batch_resp = client.post(
            "/api/sync/bookmarks/batch",
            json={
                "user_id": "u1",
                "device_id": "android-01",
                "items": [
                    {
                        "bookmark_id": "bm-1",
                        "book_key": book_key,
                        "book_url": "https://book.example/1",
                        "source_url": "https://source.example",
                        "book_name": "Book 1",
                        "chapter_idx": 1,
                        "chapter_title": "Chapter 1",
                        "chapter_url": "https://book.example/1/1",
                        "position": 0.2,
                        "quote_text": "first quote",
                        "note": "note-1",
                        "deleted": False,
                    },
                    {
                        "bookmark_id": "bm-2",
                        "book_key": book_key,
                        "book_url": "https://book.example/1",
                        "source_url": "https://source.example",
                        "book_name": "Book 1",
                        "chapter_idx": 2,
                        "chapter_title": "Chapter 2",
                        "chapter_url": "https://book.example/1/2",
                        "position": 0.45,
                        "quote_text": "second quote",
                        "note": "note-2",
                        "deleted": False,
                    },
                ],
            },
        )
        assert batch_resp.status_code == 200
        batch_body = batch_resp.json()
        assert len(batch_body["items"]) == 2
        assert batch_body["next_cursor"] == batch_body["items"][-1]["revision"]
        first_cursor = batch_body["next_cursor"]

        pull_resp = client.get(
            "/api/sync/bookmarks/pull",
            params={"user_id": "u1", "since": 0, "limit": 100},
        )
        assert pull_resp.status_code == 200
        pull_items = pull_resp.json()["items"]
        assert len(pull_items) == 2
        assert pull_items[0]["bookmark_id"] == "bm-1"
        assert pull_items[1]["bookmark_id"] == "bm-2"
        assert pull_items[0]["book_key"] == book_key

        update_resp = client.post(
            "/api/sync/bookmarks/batch",
            json={
                "user_id": "u1",
                "device_id": "android-02",
                "items": [
                    {
                        "bookmark_id": "bm-2",
                        "book_key": book_key,
                        "book_url": "https://book.example/1",
                        "source_url": "https://source.example",
                        "book_name": "Book 1",
                        "chapter_idx": 2,
                        "chapter_title": "Chapter 2",
                        "chapter_url": "https://book.example/1/2",
                        "position": 0.46,
                        "quote_text": "second quote",
                        "note": "note-2-updated",
                        "deleted": True,
                    }
                ],
            },
        )
        assert update_resp.status_code == 200
        update_body = update_resp.json()
        assert len(update_body["items"]) == 1
        assert update_body["items"][0]["deleted"] is True

        delta_pull_resp = client.get(
            "/api/sync/bookmarks/pull",
            params={"user_id": "u1", "since": first_cursor, "limit": 100},
        )
        assert delta_pull_resp.status_code == 200
        delta_items = delta_pull_resp.json()["items"]
        assert len(delta_items) == 1
        assert delta_items[0]["bookmark_id"] == "bm-2"
        assert delta_items[0]["deleted"] is True
        assert delta_items[0]["note"] == "note-2-updated"


def test_offline_task_builds_catalog_for_device(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    with TestClient(app) as client:
        create_task_resp = client.post(
            "/api/offline/tasks",
            json={
                "user_id": "u1",
                "device_id": "eink-01",
                "book_id": book_id,
            },
        )
        assert create_task_resp.status_code == 200
        created_task = create_task_resp.json()
        assert created_task["status"] in {"queued", "running", "completed"}
        assert 0 <= created_task["progress"] <= 100

        task = _wait_for_offline_task(client, created_task["task_id"])
        assert task["status"] == "completed"
        assert task["cached_chapters"] == 1

        catalog_resp = client.get("/api/offline/catalog", params={"user_id": "u1", "device_id": "eink-01"})
        assert catalog_resp.status_code == 200
        catalog = catalog_resp.json()
        assert len(catalog) == 1
        assert catalog[0]["book_id"] == book_id
        assert catalog[0]["cached_chapters"] == 1


def test_offline_tasks_list_includes_latest_failed_task(tmp_path, monkeypatch):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    async def fake_ensure_book_cached(_book_id: int):
        return {"ok": False, "error": "network timeout", "cached": 0, "total": 1}

    monkeypatch.setattr("backend.services.sync_manager.ensure_book_cached", fake_ensure_book_cached)

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/offline/tasks",
            json={
                "user_id": "u1",
                "device_id": "android-01",
                "book_id": book_id,
            },
        )
        assert create_resp.status_code == 200
        created_task = create_resp.json()
        assert created_task["status"] in {"queued", "running", "failed"}

        task_body = _wait_for_offline_task(client, created_task["task_id"])
        assert task_body["status"] == "failed"

        list_resp = client.get(
            "/api/offline/tasks",
            params={"user_id": "u1", "device_id": "android-01", "limit": 20},
        )
        assert list_resp.status_code == 200
        tasks = list_resp.json()
        assert len(tasks) == 1
        assert tasks[0]["book_id"] == book_id
        assert tasks[0]["status"] == "failed"
        assert tasks[0]["book_name"] == "Offline Test Book"


def test_offline_task_create_is_idempotent_while_running(tmp_path, monkeypatch):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    async def slow_ensure_book_cached(_book_id: int):
        await asyncio.sleep(0.2)
        return {"ok": True, "cached": 1, "total": 1}

    monkeypatch.setattr("backend.services.sync_manager.ensure_book_cached", slow_ensure_book_cached)

    with TestClient(app) as client:
        first_resp = client.post(
            "/api/offline/tasks",
            json={
                "user_id": "u1",
                "device_id": "android-02",
                "book_id": book_id,
            },
        )
        assert first_resp.status_code == 200
        first_task = first_resp.json()

        second_resp = client.post(
            "/api/offline/tasks",
            json={
                "user_id": "u1",
                "device_id": "android-02",
                "book_id": book_id,
            },
        )
        assert second_resp.status_code == 200
        second_task = second_resp.json()

        assert first_task["task_id"] == second_task["task_id"]
        assert second_task["status"] in {"queued", "running", "completed"}

        final_task = _wait_for_offline_task(client, first_task["task_id"])
        assert final_task["status"] == "completed"


def test_offline_task_fails_when_worker_disabled(tmp_path):
    _setup_tmp_data(tmp_path)
    book_id = _seed_local_book()

    previous_enabled = settings.offline_task_worker_enabled
    settings.offline_task_worker_enabled = False
    try:
        with TestClient(app) as client:
            create_resp = client.post(
                "/api/offline/tasks",
                json={
                    "user_id": "u1",
                    "device_id": "android-03",
                    "book_id": book_id,
                },
            )
            assert create_resp.status_code == 200
            task = create_resp.json()
            assert task["status"] == "failed"
            assert task["error_message"] == "offline task worker unavailable"
            assert task["progress"] == 100
    finally:
        settings.offline_task_worker_enabled = previous_enabled
