from __future__ import annotations

import asyncio
import uuid

from fastapi import HTTPException

from backend.config import settings
from backend.database import get_db
from backend.models.sync import OfflineTaskCreateRequest, SyncBookmarksBatchRequest, SyncProgressUpsertRequest
from backend.services.book_manager import ensure_book_cached

PROGRESS_POSITION_CONFLICT_THRESHOLD = 0.10
OFFLINE_TERMINAL_STATUSES = {"completed", "failed"}
OFFLINE_TASK_WORKER_UNAVAILABLE = "offline task worker unavailable"
_OFFLINE_TASK_RUNNERS: dict[str, asyncio.Task[None]] = {}


def _serialize_progress(
    row,
    *,
    accepted: bool = True,
    conflict: bool = False,
    conflict_reason: str = "",
) -> dict:
    item = dict(row)
    item["accepted"] = accepted
    item["conflict"] = conflict
    item["conflict_reason"] = conflict_reason
    return item


def _is_progress_stale(existing_row, payload: SyncProgressUpsertRequest) -> tuple[bool, str]:
    existing_chapter = int(existing_row["chapter_idx"])
    existing_position = float(existing_row["position"])

    if payload.chapter_idx < existing_chapter:
        return True, "chapter_regression"

    if (
        payload.chapter_idx == existing_chapter
        and payload.position + PROGRESS_POSITION_CONFLICT_THRESHOLD < existing_position
    ):
        return True, "position_regression"

    return False, ""


def _serialize_bookmark(row) -> dict:
    item = dict(row)
    item["deleted"] = bool(item.get("deleted", 0))
    return item


def _clamp_progress(cached_chapters: int, total_chapters: int, status: str) -> int:
    cached = max(0, int(cached_chapters or 0))
    total = max(0, int(total_chapters or 0))
    if total > 0:
        return max(0, min(100, int((cached * 100) / total)))
    if status in OFFLINE_TERMINAL_STATUSES:
        return 100
    return 0


def _serialize_offline_task(row) -> dict:
    item = dict(row)
    total = int(item.get("total_chapters") or 0)
    cached = int(item.get("cached_chapters") or 0)
    status = item.get("status") or "queued"
    progress = item.get("progress")
    item["total_chapters"] = total
    item["cached_chapters"] = cached
    item["progress"] = (
        _clamp_progress(cached, total, status)
        if progress is None
        else max(0, min(100, int(progress)))
    )
    return item


async def upsert_progress(payload: SyncProgressUpsertRequest) -> dict:
    db = await get_db()

    book_key = payload.book_key.strip()
    book_url = payload.book_url
    source_url = payload.source_url

    existing_cursor = await db.execute(
        """SELECT user_id, device_id, book_key, book_url, source_url, book_name, chapter_idx,
        chapter_title, chapter_url, position, revision, updated_at
        FROM sync_progress WHERE user_id = ? AND book_key = ?""",
        (payload.user_id, book_key),
    )
    existing_row = await existing_cursor.fetchone()
    if existing_row and not payload.force:
        stale, reason = _is_progress_stale(existing_row, payload)
        if stale:
            return _serialize_progress(
                existing_row,
                accepted=False,
                conflict=True,
                conflict_reason=reason,
            )

    revision_cursor = await db.execute("SELECT COALESCE(MAX(revision), 0) AS max_revision FROM sync_progress")
    next_revision = (await revision_cursor.fetchone())["max_revision"] + 1

    await db.execute(
        """INSERT INTO sync_progress
        (user_id, book_key, book_url, source_url, book_name, chapter_idx, chapter_title, chapter_url, position, device_id, updated_at, revision)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        ON CONFLICT(user_id, book_key) DO UPDATE SET
            book_url = excluded.book_url,
            source_url = excluded.source_url,
            book_name = excluded.book_name,
            chapter_idx = excluded.chapter_idx,
            chapter_title = excluded.chapter_title,
            chapter_url = excluded.chapter_url,
            position = excluded.position,
            device_id = excluded.device_id,
            updated_at = excluded.updated_at,
            revision = excluded.revision""",
        (
            payload.user_id,
            book_key,
            book_url,
            source_url,
            payload.book_name,
            payload.chapter_idx,
            payload.chapter_title,
            payload.chapter_url,
            payload.position,
            payload.device_id,
            next_revision,
        ),
    )

    await db.commit()

    row_cursor = await db.execute(
        """SELECT user_id, device_id, book_key, book_url, source_url, book_name, chapter_idx,
        chapter_title, chapter_url, position, revision, updated_at
        FROM sync_progress WHERE user_id = ? AND book_key = ?""",
        (payload.user_id, book_key),
    )
    row = await row_cursor.fetchone()
    return _serialize_progress(row)


async def pull_progress(user_id: str, since: int, limit: int) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """SELECT user_id, device_id, book_key, book_url, source_url, book_name, chapter_idx,
        chapter_title, chapter_url, position, revision, updated_at
        FROM sync_progress
        WHERE user_id = ? AND revision > ?
        ORDER BY revision ASC
        LIMIT ?""",
        (user_id, max(since, 0), max(1, min(limit, 200))),
    )
    rows = await cursor.fetchall()
    items = [_serialize_progress(row) for row in rows]
    next_cursor = since
    if items:
        next_cursor = items[-1]["revision"]
    return {"items": items, "next_cursor": next_cursor}


async def upsert_bookmarks_batch(payload: SyncBookmarksBatchRequest) -> dict:
    db = await get_db()

    revision_cursor = await db.execute("SELECT COALESCE(MAX(revision), 0) AS max_revision FROM sync_bookmarks")
    next_revision = (await revision_cursor.fetchone())["max_revision"]

    for item in payload.items:
        next_revision += 1
        book_key = item.book_key.strip()
        book_url = item.book_url
        source_url = item.source_url
        await db.execute(
            """INSERT INTO sync_bookmarks
            (user_id, bookmark_id, book_key, book_url, source_url, book_name, chapter_idx, chapter_title,
            chapter_url, position, quote_text, note, device_id, deleted, updated_at, revision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(user_id, bookmark_id) DO UPDATE SET
                book_key = excluded.book_key,
                book_url = excluded.book_url,
                source_url = excluded.source_url,
                book_name = excluded.book_name,
                chapter_idx = excluded.chapter_idx,
                chapter_title = excluded.chapter_title,
                chapter_url = excluded.chapter_url,
                position = excluded.position,
                quote_text = excluded.quote_text,
                note = excluded.note,
                device_id = excluded.device_id,
                deleted = excluded.deleted,
                updated_at = excluded.updated_at,
                revision = excluded.revision""",
            (
                payload.user_id,
                item.bookmark_id,
                book_key,
                book_url,
                source_url,
                item.book_name,
                item.chapter_idx,
                item.chapter_title,
                item.chapter_url,
                item.position,
                item.quote_text,
                item.note,
                payload.device_id,
                int(item.deleted),
                next_revision,
            ),
        )

    await db.commit()

    bookmark_ids = list(dict.fromkeys(item.bookmark_id for item in payload.items))
    if not bookmark_ids:
        return {"items": [], "next_cursor": next_revision}

    placeholders = ",".join("?" for _ in bookmark_ids)
    cursor = await db.execute(
        f"""SELECT user_id, device_id, bookmark_id, book_key, book_url, source_url, book_name,
        chapter_idx, chapter_title, chapter_url, position, quote_text, note,
        deleted, revision, updated_at
        FROM sync_bookmarks
        WHERE user_id = ? AND bookmark_id IN ({placeholders})
        ORDER BY revision ASC""",
        (payload.user_id, *bookmark_ids),
    )
    rows = await cursor.fetchall()
    items = [_serialize_bookmark(row) for row in rows]
    response_cursor = items[-1]["revision"] if items else next_revision
    return {"items": items, "next_cursor": response_cursor}


async def pull_bookmarks(user_id: str, since: int, limit: int) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """SELECT user_id, device_id, bookmark_id, book_key, book_url, source_url, book_name,
        chapter_idx, chapter_title, chapter_url, position, quote_text, note,
        deleted, revision, updated_at
        FROM sync_bookmarks
        WHERE user_id = ? AND revision > ?
        ORDER BY revision ASC
        LIMIT ?""",
        (user_id, max(since, 0), max(1, min(limit, 200))),
    )
    rows = await cursor.fetchall()
    items = [_serialize_bookmark(row) for row in rows]
    next_cursor = since
    if items:
        next_cursor = items[-1]["revision"]
    return {"items": items, "next_cursor": next_cursor}


async def create_offline_download_task(payload: OfflineTaskCreateRequest) -> dict:
    db = await get_db()

    book_row = await _resolve_book(payload)
    active_task_cursor = await db.execute(
        """SELECT task_id FROM offline_download_tasks
        WHERE user_id = ? AND device_id = ? AND book_key = ? AND status IN ('queued', 'running')
        ORDER BY created_at DESC
        LIMIT 1""",
        (payload.user_id, payload.device_id, book_row["book_key"]),
    )
    active_task_row = await active_task_cursor.fetchone()
    if active_task_row:
        active_task_id = active_task_row["task_id"]
        scheduled = await _schedule_offline_task(active_task_id)
        if not scheduled:
            await _mark_task_worker_unavailable(active_task_id)
        return await get_offline_task(active_task_id)

    cached_cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM chapter_cache WHERE book_id = ?",
        (book_row["id"],),
    )
    cached_chapters = int((await cached_cursor.fetchone())["cnt"])

    total_chapters = int(book_row["total_chapters"] or 0)
    if total_chapters <= 0:
        total_cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM chapters WHERE book_id = ?",
            (book_row["id"],),
        )
        total_chapters = int((await total_cursor.fetchone())["cnt"])

    task_id = uuid.uuid4().hex
    progress = _clamp_progress(cached_chapters, total_chapters, "queued")

    await db.execute(
        """INSERT INTO offline_download_tasks
        (task_id, user_id, device_id, book_id, book_key, book_url, source_url,
        status, progress, total_chapters, cached_chapters, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, datetime('now'), datetime('now'))""",
        (
            task_id,
            payload.user_id,
            payload.device_id,
            book_row["id"],
            book_row["book_key"],
            book_row["book_url"],
            book_row["source_url"],
            progress,
            total_chapters,
            cached_chapters,
        ),
    )
    await db.commit()

    scheduled = await _schedule_offline_task(task_id)
    if not scheduled:
        await _mark_task_worker_unavailable(task_id)

    return await get_offline_task(task_id)


async def get_offline_task(task_id: str) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.task_id, t.user_id, t.device_id, t.book_id, t.book_key, COALESCE(b.name, '') AS book_name,
        t.book_url, t.source_url, t.status, t.progress,
        t.total_chapters, t.cached_chapters, t.error_message, t.created_at, t.updated_at, t.completed_at
        FROM offline_download_tasks t
        LEFT JOIN books b ON b.id = t.book_id
        WHERE t.task_id = ?""",
        (task_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_offline_task(row)


async def list_offline_tasks(user_id: str, device_id: str, limit: int = 200) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.task_id, t.user_id, t.device_id, t.book_id, t.book_key, COALESCE(b.name, '') AS book_name,
        t.book_url, t.source_url, t.status, t.progress, t.total_chapters, t.cached_chapters,
        t.error_message, t.created_at, t.updated_at, t.completed_at
        FROM offline_download_tasks t
        LEFT JOIN books b ON b.id = t.book_id
        WHERE t.user_id = ? AND t.device_id = ?
        ORDER BY t.updated_at DESC
        LIMIT ?""",
        (user_id, device_id, max(1, min(limit, 500))),
    )
    rows = await cursor.fetchall()
    return [_serialize_offline_task(row) for row in rows]


async def list_offline_catalog(user_id: str, device_id: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.user_id, t.device_id, t.book_id, t.book_key, t.book_url, t.source_url,
        COALESCE(b.name, '') AS name,
        COALESCE(b.author, '') AS author,
        CASE
            WHEN COALESCE(b.total_chapters, 0) > 0 THEN b.total_chapters
            ELSE COALESCE(ch.total_chapters, 0)
        END AS total_chapters,
        COALESCE(cc.cached_chapters, 0) AS cached_chapters,
        t.updated_at
        FROM offline_download_tasks t
        INNER JOIN (
            SELECT MAX(rowid) AS row_id
            FROM offline_download_tasks
            WHERE user_id = ? AND device_id = ? AND status = 'completed'
            GROUP BY book_key
        ) latest ON latest.row_id = t.rowid
        LEFT JOIN books b ON b.id = t.book_id
        LEFT JOIN (
            SELECT book_id, COUNT(*) AS cached_chapters
            FROM chapter_cache
            GROUP BY book_id
        ) cc ON cc.book_id = t.book_id
        LEFT JOIN (
            SELECT book_id, COUNT(*) AS total_chapters
            FROM chapters
            GROUP BY book_id
        ) ch ON ch.book_id = t.book_id
        WHERE t.user_id = ? AND t.device_id = ? AND COALESCE(cc.cached_chapters, 0) > 0
        ORDER BY t.updated_at DESC""",
        (user_id, device_id, user_id, device_id),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def bootstrap_offline_task_worker() -> None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT task_id
        FROM offline_download_tasks
        WHERE status IN ('queued', 'running')
        ORDER BY created_at ASC"""
    )
    rows = await cursor.fetchall()

    for row in rows:
        task_id = row["task_id"]
        scheduled = await _schedule_offline_task(task_id)
        if not scheduled:
            await _mark_task_worker_unavailable(task_id)


async def shutdown_offline_task_worker() -> None:
    running = [task for task in _OFFLINE_TASK_RUNNERS.values() if not task.done()]
    for task in running:
        task.cancel()

    if running:
        await asyncio.gather(*running, return_exceptions=True)

    _OFFLINE_TASK_RUNNERS.clear()


async def _schedule_offline_task(task_id: str) -> bool:
    if not settings.offline_task_worker_enabled:
        return False

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False

    existing = _OFFLINE_TASK_RUNNERS.get(task_id)
    if existing and not existing.done():
        return True

    async def _runner():
        try:
            await _run_offline_task(task_id)
        finally:
            _OFFLINE_TASK_RUNNERS.pop(task_id, None)

    _OFFLINE_TASK_RUNNERS[task_id] = loop.create_task(_runner())
    return True


async def _run_offline_task(task_id: str) -> None:
    db = await get_db()
    task_cursor = await db.execute(
        "SELECT task_id, book_id, status FROM offline_download_tasks WHERE task_id = ?",
        (task_id,),
    )
    task_row = await task_cursor.fetchone()
    if not task_row:
        return
    if task_row["status"] in OFFLINE_TERMINAL_STATUSES:
        return

    await db.execute(
        """UPDATE offline_download_tasks
        SET status = 'running',
            progress = CASE WHEN progress < 1 THEN 1 ELSE progress END,
            error_message = '',
            updated_at = datetime('now')
        WHERE task_id = ?""",
        (task_id,),
    )
    await db.commit()

    try:
        cache_result = await ensure_book_cached(int(task_row["book_id"]))
    except Exception as exc:  # defensive guard for network/parser failures
        cache_result = {"ok": False, "error": str(exc), "cached": 0, "total": 0}

    status = "completed" if cache_result.get("ok") else "failed"
    error_message = cache_result.get("error", "") if status == "failed" else ""
    cached = int(cache_result.get("cached", 0))
    total = int(cache_result.get("total", 0))
    progress = _clamp_progress(cached, total, status)

    await db.execute(
        """UPDATE offline_download_tasks
        SET status = ?, progress = ?, total_chapters = ?, cached_chapters = ?, error_message = ?,
            updated_at = datetime('now'), completed_at = datetime('now')
        WHERE task_id = ?""",
        (status, progress, total, cached, error_message, task_id),
    )
    await db.commit()


async def _mark_task_worker_unavailable(task_id: str) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE offline_download_tasks
        SET status = 'failed', progress = 100, error_message = ?,
            updated_at = datetime('now'), completed_at = datetime('now')
        WHERE task_id = ? AND status IN ('queued', 'running')""",
        (OFFLINE_TASK_WORKER_UNAVAILABLE, task_id),
    )
    await db.commit()


async def _resolve_book(payload: OfflineTaskCreateRequest):
    db = await get_db()
    if payload.book_key:
        cursor = await db.execute("SELECT * FROM books WHERE book_key = ?", (payload.book_key,))
    elif payload.book_id is not None:
        cursor = await db.execute("SELECT * FROM books WHERE id = ?", (payload.book_id,))
    else:
        raise HTTPException(status_code=400, detail="Provide book_id or book_key")

    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return row
