from __future__ import annotations

import asyncio
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from backend.config import settings
from backend.database import get_db

BACKUP_FORMAT_VERSION = "2026-06-12"
RESTORE_MODES = {"full", "incremental"}
CONFLICT_POLICIES = {"backup_wins", "local_wins", "newer_wins"}

BACKUP_TABLES = [
    "book_sources",
    "book_categories",
    "books",
    "chapters",
    "chapter_cache",
    "user_settings",
    "sync_progress",
    "sync_bookmarks",
    "offline_download_tasks",
    "offline_catalog",
]

AUTOINCREMENT_TABLES = ["books", "chapters", "chapter_cache", "offline_catalog"]
FILE_BUCKETS = {
    "fonts": "files/fonts",
    "exports": "files/exports",
}

_BACKUP_LOCK = asyncio.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_relative_path(raw_path: str) -> str | None:
    pure = PurePosixPath(raw_path)
    if pure.is_absolute():
        return None

    parts = [part for part in pure.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None

    return str(PurePosixPath(*parts))


def _resolve_target_path(base_dir: Path, relative_path: str) -> Path:
    target = (base_dir / relative_path).resolve()
    base = base_dir.resolve()
    if target == base or base in target.parents:
        return target
    raise ValueError("Unsafe backup file path")


async def _get_table_columns(db, table_name: str) -> list[str]:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return [row["name"] for row in rows]


async def _get_primary_key_columns(db, table_name: str) -> list[str]:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    ordered = sorted((row for row in rows if int(row["pk"] or 0) > 0), key=lambda row: int(row["pk"]))
    return [row["name"] for row in ordered]


def _is_backup_row_newer(table_name: str, backup_row: dict, local_row: dict) -> bool:
    if "revision" in backup_row and "revision" in local_row:
        try:
            return int(backup_row["revision"] or 0) >= int(local_row["revision"] or 0)
        except (TypeError, ValueError):
            return False

    for field in ("updated_at", "cached_at", "added_at", "created_at", "completed_at"):
        if field not in backup_row or field not in local_row:
            continue

        backup_dt = _parse_iso_datetime(str(backup_row.get(field) or ""))
        local_dt = _parse_iso_datetime(str(local_row.get(field) or ""))
        if backup_dt and local_dt:
            return backup_dt >= local_dt

    if table_name in {"chapters", "chapter_cache"}:
        return True

    return False


def _rows_equal_by_columns(local_row: dict, backup_row: dict, columns: list[str]) -> bool:
    for column in columns:
        if local_row.get(column) != backup_row.get(column):
            return False
    return True


async def _insert_row(db, table_name: str, row: dict, columns: list[str]) -> None:
    if not columns:
        return
    placeholders = ", ".join("?" for _ in columns)
    quoted_columns = ", ".join(columns)
    values = [row.get(column) for column in columns]
    await db.execute(
        f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders})",
        values,
    )


async def _update_row(db, table_name: str, row: dict, primary_keys: list[str], columns: list[str]) -> None:
    update_columns = [column for column in columns if column not in primary_keys]
    if not update_columns:
        return

    set_clause = ", ".join(f"{column} = ?" for column in update_columns)
    where_clause = " AND ".join(f"{column} = ?" for column in primary_keys)
    values = [row.get(column) for column in update_columns]
    values.extend(row.get(column) for column in primary_keys)

    await db.execute(f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}", values)


async def _fetch_existing_row(db, table_name: str, row: dict, primary_keys: list[str]):
    where_clause = " AND ".join(f"{column} = ?" for column in primary_keys)
    values = [row.get(column) for column in primary_keys]
    cursor = await db.execute(f"SELECT * FROM {table_name} WHERE {where_clause}", values)
    existing = await cursor.fetchone()
    return dict(existing) if existing else None


async def _reset_autoincrement_sequences(db) -> None:
    for table_name in AUTOINCREMENT_TABLES:
        cursor = await db.execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {table_name}")
        row = await cursor.fetchone()
        max_id = int(row["max_id"] or 0)
        await db.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))
        if max_id > 0:
            await db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table_name, max_id))


async def create_backup_archive() -> tuple[str, bytes]:
    async with _BACKUP_LOCK:
        db = await get_db()

        table_snapshot: dict[str, list[dict]] = {}
        table_counts: dict[str, int] = {}

        for table_name in BACKUP_TABLES:
            cursor = await db.execute(f"SELECT * FROM {table_name}")
            rows = [dict(row) for row in await cursor.fetchall()]
            table_snapshot[table_name] = rows
            table_counts[table_name] = len(rows)

        snapshot_payload = {
            "format_version": BACKUP_FORMAT_VERSION,
            "created_at": _utc_now_iso(),
            "tables": table_snapshot,
        }

        file_entries: list[dict] = []
        buffer = io.BytesIO()

        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("snapshot.json", json.dumps(snapshot_payload, ensure_ascii=False))

            for bucket_name, archive_prefix in FILE_BUCKETS.items():
                if bucket_name == "fonts":
                    source_dir = settings.font_dir
                else:
                    source_dir = settings.export_dir

                if not source_dir.exists():
                    continue

                for file_path in sorted(source_dir.rglob("*")):
                    if not file_path.is_file():
                        continue

                    relative_path = file_path.relative_to(source_dir).as_posix()
                    archive_path = f"{archive_prefix}/{relative_path}"
                    content = file_path.read_bytes()
                    archive.writestr(archive_path, content)
                    file_entries.append(
                        {
                            "bucket": bucket_name,
                            "path": relative_path,
                            "size": len(content),
                            "sha256": _sha256_bytes(content),
                        }
                    )

            manifest_payload = {
                "format_version": BACKUP_FORMAT_VERSION,
                "created_at": snapshot_payload["created_at"],
                "tables": table_counts,
                "files": file_entries,
            }
            archive.writestr("manifest.json", json.dumps(manifest_payload, ensure_ascii=False))

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_name = f"easyreader-backup-{timestamp}.zip"
        return file_name, buffer.getvalue()


async def _restore_tables_full(db, snapshot_tables: dict[str, list[dict]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    await db.execute("PRAGMA foreign_keys=OFF")

    try:
        await db.execute("BEGIN")

        for table_name in reversed(BACKUP_TABLES):
            await db.execute(f"DELETE FROM {table_name}")

        for table_name in BACKUP_TABLES:
            incoming_rows = snapshot_tables.get(table_name) or []
            if not isinstance(incoming_rows, list):
                raise ValueError(f"Invalid backup payload for table: {table_name}")

            table_columns = await _get_table_columns(db, table_name)
            inserted = 0

            for item in incoming_rows:
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid row payload in table: {table_name}")

                filtered_row = {key: value for key, value in item.items() if key in table_columns}
                await _insert_row(db, table_name, filtered_row, list(filtered_row.keys()))
                inserted += 1

            summary[table_name] = {
                "incoming": len(incoming_rows),
                "inserted": inserted,
                "updated": 0,
                "skipped": 0,
                "conflicts": 0,
                "resolved_with_backup": 0,
                "resolved_with_local": 0,
            }

        await _reset_autoincrement_sequences(db)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.execute("PRAGMA foreign_keys=ON")

    return summary


async def _restore_tables_incremental(
    db,
    snapshot_tables: dict[str, list[dict]],
    conflict_policy: str,
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    await db.execute("BEGIN")

    try:
        for table_name in BACKUP_TABLES:
            incoming_rows = snapshot_tables.get(table_name) or []
            if not isinstance(incoming_rows, list):
                raise ValueError(f"Invalid backup payload for table: {table_name}")

            table_columns = await _get_table_columns(db, table_name)
            primary_keys = await _get_primary_key_columns(db, table_name)
            if not primary_keys:
                raise ValueError(f"Table without primary key is not supported: {table_name}")

            inserted = 0
            updated = 0
            skipped = 0
            conflicts = 0
            resolved_with_backup = 0
            resolved_with_local = 0

            for item in incoming_rows:
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid row payload in table: {table_name}")

                filtered_row = {key: value for key, value in item.items() if key in table_columns}

                if any(filtered_row.get(pk) is None for pk in primary_keys):
                    skipped += 1
                    continue

                existing_row = await _fetch_existing_row(db, table_name, filtered_row, primary_keys)

                if existing_row is None:
                    await _insert_row(db, table_name, filtered_row, list(filtered_row.keys()))
                    inserted += 1
                    continue

                compare_columns = list(filtered_row.keys())
                if _rows_equal_by_columns(existing_row, filtered_row, compare_columns):
                    skipped += 1
                    continue

                conflicts += 1

                if conflict_policy == "local_wins":
                    skipped += 1
                    resolved_with_local += 1
                    continue

                if conflict_policy == "newer_wins" and not _is_backup_row_newer(table_name, filtered_row, existing_row):
                    skipped += 1
                    resolved_with_local += 1
                    continue

                await _update_row(db, table_name, filtered_row, primary_keys, list(filtered_row.keys()))
                updated += 1
                resolved_with_backup += 1

            summary[table_name] = {
                "incoming": len(incoming_rows),
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "conflicts": conflicts,
                "resolved_with_backup": resolved_with_backup,
                "resolved_with_local": resolved_with_local,
            }

        await _reset_autoincrement_sequences(db)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return summary


def _clear_directory(dir_path: Path) -> None:
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)


def _restore_files_from_archive(archive: ZipFile, restore_mode: str, conflict_policy: str) -> dict[str, dict[str, int]]:
    summary = {
        "fonts": {
            "incoming": 0,
            "written": 0,
            "skipped": 0,
            "conflicts": 0,
            "resolved_with_backup": 0,
            "resolved_with_local": 0,
        },
        "exports": {
            "incoming": 0,
            "written": 0,
            "skipped": 0,
            "conflicts": 0,
            "resolved_with_backup": 0,
            "resolved_with_local": 0,
        },
    }

    target_dirs = {
        "fonts": settings.font_dir,
        "exports": settings.export_dir,
    }

    for target in target_dirs.values():
        target.mkdir(parents=True, exist_ok=True)

    if restore_mode == "full":
        for target in target_dirs.values():
            _clear_directory(target)

    for info in archive.infolist():
        if info.is_dir():
            continue

        zip_path = PurePosixPath(info.filename)
        parts = zip_path.parts
        if len(parts) < 3 or parts[0] != "files":
            continue

        bucket_name = parts[1]
        if bucket_name not in summary:
            continue

        relative_raw = str(PurePosixPath(*parts[2:]))
        relative_path = _safe_relative_path(relative_raw)
        if not relative_path:
            continue

        summary[bucket_name]["incoming"] += 1
        target_root = target_dirs[bucket_name]
        target_path = _resolve_target_path(target_root, relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        content = archive.read(info.filename)

        if target_path.exists() and restore_mode == "incremental":
            local_content = target_path.read_bytes()
            if _sha256_bytes(local_content) == _sha256_bytes(content):
                summary[bucket_name]["skipped"] += 1
                continue

            summary[bucket_name]["conflicts"] += 1

            if conflict_policy == "local_wins":
                summary[bucket_name]["skipped"] += 1
                summary[bucket_name]["resolved_with_local"] += 1
                continue

            if conflict_policy == "newer_wins":
                archive_dt = datetime(*info.date_time, tzinfo=timezone.utc)
                local_dt = datetime.fromtimestamp(target_path.stat().st_mtime, tz=timezone.utc)
                if archive_dt < local_dt:
                    summary[bucket_name]["skipped"] += 1
                    summary[bucket_name]["resolved_with_local"] += 1
                    continue

        target_path.write_bytes(content)
        summary[bucket_name]["written"] += 1
        summary[bucket_name]["resolved_with_backup"] += 1

    return summary


async def restore_backup_archive(raw_archive: bytes, restore_mode: str, conflict_policy: str) -> dict:
    if restore_mode not in RESTORE_MODES:
        raise ValueError("Unsupported restore mode")
    if conflict_policy not in CONFLICT_POLICIES:
        raise ValueError("Unsupported conflict policy")
    if not raw_archive:
        raise ValueError("Empty backup archive")

    try:
        archive = ZipFile(io.BytesIO(raw_archive), mode="r")
    except BadZipFile as exc:
        raise ValueError("Backup file is not a valid zip archive") from exc

    with archive:
        if "snapshot.json" not in archive.namelist():
            raise ValueError("Backup archive missing snapshot.json")

        try:
            snapshot_payload = json.loads(archive.read("snapshot.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid backup snapshot payload") from exc

        format_version = str(snapshot_payload.get("format_version") or "")
        if not format_version:
            raise ValueError("Backup snapshot missing format version")

        snapshot_tables = snapshot_payload.get("tables")
        if not isinstance(snapshot_tables, dict):
            raise ValueError("Backup snapshot missing tables payload")

        async with _BACKUP_LOCK:
            db = await get_db()
            if restore_mode == "full":
                table_summary = await _restore_tables_full(db, snapshot_tables)
            else:
                table_summary = await _restore_tables_incremental(db, snapshot_tables, conflict_policy)

            file_summary = _restore_files_from_archive(archive, restore_mode, conflict_policy)

    total_conflicts = 0
    for entry in table_summary.values():
        total_conflicts += int(entry.get("conflicts", 0))
    for entry in file_summary.values():
        total_conflicts += int(entry.get("conflicts", 0))

    return {
        "ok": True,
        "format_version": format_version,
        "mode": restore_mode,
        "conflict_policy": conflict_policy,
        "conflicts": total_conflicts,
        "tables": table_summary,
        "files": file_summary,
    }