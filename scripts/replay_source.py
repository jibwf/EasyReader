#!/usr/bin/env python3
"""Capture a real source search/TOC/content run as offline replay fixtures.

Example:
    python scripts/replay_source.py --keyword 三体 --source-name 起点
    python scripts/replay_source.py --keyword 斗破 --source-url https://example.com --chapter-index 0
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import close_db
from backend.engine.fetcher import close_client, fetch as real_fetch
from backend.engine.js_engine import parse_tauri_metadata
from backend.models.book import SearchResultItem
from backend.models.source import BookSourceSchema
from backend.services import content as content_service
from backend.services import search as search_service
from backend.services.source_manager import list_sources


DEFAULT_OUTPUT_DIR = Path("tests/fixtures/replays")


@dataclass
class FetchRecord:
    label: str
    url: str
    method: str
    headers: dict[str, Any]
    body: str | None
    encoding: str | None
    response_file: str
    response_sha256: str
    response_chars: int
    error: str | None = None


@dataclass
class FetchRecorder:
    output_dir: Path
    records: list[FetchRecord] = field(default_factory=list)

    async def fetch(self, url: str, **kwargs) -> str:
        method = kwargs.get("method", "GET")
        headers = kwargs.get("headers") or {}
        body = kwargs.get("body")
        encoding = kwargs.get("encoding")
        try:
            text = await real_fetch(
                url,
                method=method,
                headers=headers,
                body=body,
                use_cache=False,
                encoding=encoding,
            )
        except Exception as exc:
            self.records.append(
                FetchRecord(
                    label=kwargs.get("label", ""),
                    url=url,
                    method=method,
                    headers=headers,
                    body=body,
                    encoding=encoding,
                    response_file="",
                    response_sha256="",
                    response_chars=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            raise
        response_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        file_name = f"{len(self.records) + 1:02d}-{response_hash[:12]}.txt"
        response_path = self.output_dir / file_name
        response_path.write_text(text, encoding="utf-8")
        self.records.append(
            FetchRecord(
                label=kwargs.get("label", ""),
                url=url,
                method=method,
                headers=headers,
                body=body,
                encoding=encoding,
                response_file=file_name,
                response_sha256=response_hash,
                response_chars=len(text),
            )
        )
        return text


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    return text.strip("-")[:80] or "source"


def _redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() in {"cookie", "authorization", "proxy-authorization"}:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


def _redact_source_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict) and isinstance(data.get("header"), str):
        try:
            headers = json.loads(data["header"])
        except json.JSONDecodeError:
            data["header"] = "<redacted>" if "cookie" in data["header"].lower() else data["header"]
        else:
            data["header"] = json.dumps(_redact_headers(headers), ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2)


async def _find_source(source_url: str | None, source_name: str | None):
    sources = await list_sources(enabled_only=False)
    if source_url:
        matches = [source for source in sources if source.book_source_url == source_url]
    elif source_name:
        lowered = source_name.lower()
        matches = [source for source in sources if lowered in source.book_source_name.lower()]
    else:
        matches = []
    if not matches:
        return None
    if len(matches) > 1:
        names = ", ".join(f"{source.book_source_name} <{source.book_source_url}>" for source in matches[:5])
        raise SystemExit(f"Matched multiple sources; use --source-url. Matches: {names}")
    return matches[0]


def _source_from_db_row(source_db) -> tuple[str, str, str, BookSourceSchema | None]:
    raw = source_db.source_json
    is_tauri = raw.strip().startswith("//") or "function search" in raw[:500]
    if is_tauri:
        meta = parse_tauri_metadata(raw)
        return raw, "tauri", meta.get("name", source_db.book_source_name), None
    source = BookSourceSchema.model_validate(json.loads(raw))
    return raw, "legado", source.bookSourceName or source_db.book_source_name, source


async def capture(args: argparse.Namespace) -> Path:
    source_db = await _find_source(args.source_url, args.source_name)
    if not source_db:
        raise SystemExit("No source matched. Pass --source-url or --source-name for an imported source.")

    raw_source, source_format, source_name, legado_source = _source_from_db_row(source_db)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = args.output / f"{run_id}-{_slugify(source_name)}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    recorder = FetchRecorder(snapshot_dir)
    original_search_fetch = search_service.fetch
    original_content_fetch = content_service.fetch
    search_service.fetch = recorder.fetch
    content_service.fetch = recorder.fetch

    error: str | None = None
    results = []
    selected = None
    chapters = []
    chapter_content = ""
    selected_chapter = None

    try:
        try:
            if source_format == "tauri":
                results = search_service._do_tauri_search(raw_source, source_db.book_source_url, source_name, args.keyword)
            else:
                results = await search_service._do_search(legado_source, args.keyword)

            selected = results[args.result_index] if len(results) > args.result_index else None

            if selected:
                chapters = await content_service.get_chapters(selected.book_url, selected.source_url)
                if len(chapters) > args.chapter_index:
                    selected_chapter = chapters[args.chapter_index]
                    chapter_content = await content_service.get_chapter_content(selected_chapter.url, selected.source_url)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    finally:
        search_service.fetch = original_search_fetch
        content_service.fetch = original_content_fetch
        await close_client()
        await close_db()

    source_file = snapshot_dir / "source.json" if source_format == "legado" else snapshot_dir / "source.js"
    source_file.write_text(_redact_source_json(raw_source), encoding="utf-8")

    manifest = {
        "captured_at": run_id,
        "keyword": args.keyword,
        "source": {
            "name": source_name,
            "url": source_db.book_source_url,
            "format": source_format,
            "source_file": source_file.name,
        },
        "selected_result_index": args.result_index,
        "selected_chapter_index": args.chapter_index,
        "results": [_dump_model(result) for result in results[: args.max_results]],
        "selected_result": _dump_model(selected),
        "chapters": [_dump_model(chapter) for chapter in chapters[: args.max_chapters]],
        "selected_chapter": _dump_model(selected_chapter),
        "chapter_content_preview": chapter_content[: args.preview_chars],
        "chapter_content_chars": len(chapter_content),
        "error": error,
        "fetches": [
            {
                **record.__dict__,
                "headers": _redact_headers(record.headers),
            }
            for record in recorder.records
        ],
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot_dir


async def print_sources() -> None:
    sources = await list_sources(enabled_only=False)
    try:
        for source in sources:
            print(f"{source.book_source_name}\t{source.book_source_url}\t{'enabled' if source.enabled else 'disabled'}")
    finally:
        await close_db()


def _dump_model(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, SearchResultItem):
        return value.model_dump()
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-sources", action="store_true", help="List imported sources and exit.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--source-url", help="Exact imported source URL.")
    selector.add_argument("--source-name", help="Substring match for an imported source name.")
    parser.add_argument("--keyword", help="Search keyword to replay.")
    parser.add_argument("--result-index", type=int, default=0, help="Search result index to open.")
    parser.add_argument("--chapter-index", type=int, default=0, help="Chapter index to fetch.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Snapshot output directory.")
    parser.add_argument("--max-results", type=int, default=5, help="Number of parsed results to keep in manifest.")
    parser.add_argument("--max-chapters", type=int, default=20, help="Number of parsed chapters to keep in manifest.")
    parser.add_argument("--preview-chars", type=int, default=2000, help="Chapter content preview length.")
    args = parser.parse_args()
    if not args.list_sources and not args.source_url and not args.source_name:
        parser.error("one of --source-url, --source-name, or --list-sources is required")
    if not args.list_sources and not args.keyword:
        parser.error("--keyword is required when capturing a replay")
    return args


def main() -> None:
    args = parse_args()
    if args.list_sources:
        asyncio.run(print_sources())
        return
    snapshot_dir = asyncio.run(capture(args))
    print(f"Replay fixture written to {snapshot_dir}")
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("error"):
        print(f"Capture error: {manifest['error']}")


if __name__ == "__main__":
    main()
