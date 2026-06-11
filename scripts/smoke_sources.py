#!/usr/bin/env python3
"""Run a search smoke test across imported sources.

This is intentionally lighter than replay_source.py:
- It does not save response bodies.
- It summarizes whether each source can return at least one parsed result.
- It records failure class and message so compatibility gaps can be prioritized.

Example:
    python scripts/smoke_sources.py --keyword 三体 --limit 20
    python scripts/smoke_sources.py --keyword 斗破 --format json --output smoke-report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import close_db
from backend.engine.fetcher import close_client
from backend.engine.js_engine import parse_tauri_metadata
from backend.models.source import BookSourceSchema
from backend.services import search as search_service
from backend.services.source_manager import list_sources


@dataclass
class SmokeResult:
    name: str
    url: str
    source_format: str
    status: str
    result_count: int = 0
    first_result_name: str = ""
    first_result_url: str = ""
    error_type: str = ""
    error: str = ""


async def _run_one(source_db, keyword: str, timeout: float) -> SmokeResult:
    raw = source_db.source_json
    is_tauri = raw.strip().startswith("//") or "function search" in raw[:500]
    source_format = "tauri" if is_tauri else "legado"
    source_name = source_db.book_source_name

    try:
        if is_tauri:
            meta = parse_tauri_metadata(raw)
            source_name = meta.get("name", source_name)
            results = await asyncio.wait_for(
                asyncio.to_thread(search_service._do_tauri_search, raw, source_db.book_source_url, source_name, keyword),
                timeout=timeout,
            )
        else:
            source = BookSourceSchema.model_validate(json.loads(raw))
            source_name = source.bookSourceName or source_name
            if not source.searchUrl:
                return SmokeResult(
                    name=source_name,
                    url=source_db.book_source_url,
                    source_format=source_format,
                    status="skipped",
                    error_type="NoSearchUrl",
                    error="source has no searchUrl",
                )
            results = await asyncio.wait_for(search_service._do_search(source, keyword), timeout=timeout)
    except Exception as exc:
        return SmokeResult(
            name=source_name,
            url=source_db.book_source_url,
            source_format=source_format,
            status="error",
            error_type=type(exc).__name__,
            error=str(exc),
        )

    usable_results = [result for result in results if result.book_url]
    first = usable_results[0] if usable_results else None
    return SmokeResult(
        name=source_name,
        url=source_db.book_source_url,
        source_format=source_format,
        status="ok" if usable_results else "empty",
        result_count=len(usable_results),
        first_result_name=first.name if first else "",
        first_result_url=first.book_url if first else "",
    )


async def run_smoke(args: argparse.Namespace) -> dict:
    sources = await list_sources(enabled_only=not args.include_disabled)
    if args.source_name:
        lowered = args.source_name.lower()
        sources = [source for source in sources if lowered in source.book_source_name.lower()]
    if args.source_url:
        sources = [source for source in sources if source.book_source_url == args.source_url]
    if args.offset:
        sources = sources[args.offset:]
    if args.limit:
        sources = sources[: args.limit]

    sem = asyncio.Semaphore(args.concurrency)
    results: list[SmokeResult] = []

    async def worker(source_db):
        async with sem:
            result = await _run_one(source_db, args.keyword, args.timeout)
            results.append(result)
            if args.format == "text":
                print(_format_line(result), flush=True)

    try:
        await asyncio.gather(*(worker(source) for source in sources))
    finally:
        await close_client()
        await close_db()

    results.sort(key=lambda item: (item.status != "ok", item.name, item.url))
    counts = {
        "ok": sum(1 for item in results if item.status == "ok"),
        "empty": sum(1 for item in results if item.status == "empty"),
        "error": sum(1 for item in results if item.status == "error"),
        "skipped": sum(1 for item in results if item.status == "skipped"),
    }
    return {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "keyword": args.keyword,
        "source_count": len(results),
        "counts": counts,
        "results": [asdict(result) for result in results],
    }


def _format_line(result: SmokeResult) -> str:
    if result.status == "ok":
        return f"OK     {result.name} | {result.result_count} | {result.first_result_name}"
    if result.status == "empty":
        return f"EMPTY  {result.name} | no parsed results"
    if result.status == "skipped":
        return f"SKIP   {result.name} | {result.error}"
    return f"ERROR  {result.name} | {result.error_type}: {result.error}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", required=True, help="Search keyword.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of sources to test.")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N matching sources.")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent source checks.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout per source in seconds.")
    parser.add_argument("--source-name", help="Only test source names containing this text.")
    parser.add_argument("--source-url", help="Only test this exact source URL.")
    parser.add_argument("--include-disabled", action="store_true", help="Include disabled sources.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    parser.add_argument("--output", type=Path, help="Write JSON report to this file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(run_smoke(args))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Smoke report written to {args.output}")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "Summary: "
            f"{report['counts']['ok']} ok, "
            f"{report['counts']['empty']} empty, "
            f"{report['counts']['error']} error, "
            f"{report['counts']['skipped']} skipped"
        )


if __name__ == "__main__":
    main()
