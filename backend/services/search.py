"""Multi-source search service with scoring, dedupe, health and fast/full modes."""

import asyncio
import json
import logging
import re as _re
from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic, time
from typing import Literal

from backend.config import settings
from backend.database import get_db
from backend.engine.fetcher import fetch, parse_headers
from backend.engine.js_engine import TauriEngine
from backend.engine.parser import RuleParser
from backend.engine.url_parser import make_absolute_url, parse_url
from backend.models.book import SearchResultItem
from backend.models.source import BookSourceSchema
from backend.services.source_manager import list_sources
from backend.utils.book_key import build_book_key

logger = logging.getLogger(__name__)


FAST_SEARCH_TIMEOUT_SECONDS = 4.0
FULL_SEARCH_TIMEOUT_SECONDS = 15.0
FAST_SEARCH_SOURCE_LIMIT = 6
SEARCH_CACHE_TTL_SECONDS = 30
MAX_SEARCH_CACHE_ENTRIES = 200


@dataclass
class SourceHealthState:
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    avg_latency_ms: float = 0.0
    last_error: str = ""
    last_success_at: float = 0.0
    updated_at: float = 0.0

    @property
    def attempts(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.attempts <= 0:
            return 0.5
        return self.success_count / self.attempts


@dataclass
class SearchCacheEntry:
    items: list[SearchResultItem]
    expires_at: float
    created_at: float


_SOURCE_HEALTH: OrderedDict[str, SourceHealthState] = OrderedDict()
_SEARCH_CACHE: dict[str, SearchCacheEntry] = {}
MAX_SOURCE_HEALTH_ENTRIES = 500


def _evict_source_health():
    while len(_SOURCE_HEALTH) > MAX_SOURCE_HEALTH_ENTRIES:
        _SOURCE_HEALTH.popitem(last=False)


def _resolve_book_url_template(
    template: str,
    fields: dict[str, str],
    element,
    parser: RuleParser,
    base_url: str,
) -> str:
    """Resolve {{book.field}} or {{$.jsonpath}} in bookUrl templates."""
    def replacer(m: _re.Match) -> str:
        expr = m.group(1)
        if expr.startswith("book."):
            field_name = expr[5:]
            # Map Legado field names
            field_map = {
                "name": "name",
                "author": "author",
                "kind": "kind",
                "coverUrl": "cover_url",
                "bookUrl": "",
            }
            mapped = field_map.get(field_name, field_name)
            return fields.get(mapped, "")
        # Try as a rule against the element
        val = parser.parse_element(expr, element, base_url)
        return val if isinstance(val, str) else ""

    return _re.sub(r"\{\{(.+?)\}\}", replacer, template)


def _first_str(value) -> str:
    if isinstance(value, list):
        return value[0] if value else ""
    return value if isinstance(value, str) else ""


async def search_books_stream(keyword: str, source_urls: list[str] | None = None):
    """Backward-compatible full-mode wrapper."""
    async for batch in search_books_stream_v2(keyword, source_urls=source_urls, mode="full"):
        yield batch


async def search_books_stream_v2(
    keyword: str,
    source_urls: list[str] | None = None,
    mode: Literal["fast", "full"] = "full",
):
    """Stream search snapshots with dedupe + ranking under fast/full modes."""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        return

    search_mode: Literal["fast", "full"] = "fast" if mode == "fast" else "full"
    cache_key = _build_search_cache_key(normalized_keyword, source_urls, search_mode)

    last_signature: tuple[str, ...] | None = None
    merged_results: list[SearchResultItem] = []

    cached_results = _get_cached_results(cache_key)
    if cached_results:
        merged_results = list(cached_results)
        last_signature = _results_signature(merged_results)
        yield merged_results
        if search_mode == "fast":
            return

    bookshelf_results = await _search_bookshelf(normalized_keyword)
    if bookshelf_results:
        merged_results = _rank_and_dedupe_results(
            normalized_keyword,
            [*merged_results, *bookshelf_results],
        )
        signature = _results_signature(merged_results)
        if signature != last_signature:
            last_signature = signature
            yield merged_results

    sources_db = await list_sources(enabled_only=True)
    if source_urls:
        allowed_sources = {url.strip() for url in source_urls if url.strip()}
        sources_db = [source for source in sources_db if source.book_source_url in allowed_sources]

    if not sources_db:
        _set_cached_results(cache_key, merged_results)
        return

    sources_db.sort(key=_source_priority_sort_key)
    if search_mode == "fast":
        sources_db = sources_db[:FAST_SEARCH_SOURCE_LIMIT]
        timeout_seconds = FAST_SEARCH_TIMEOUT_SECONDS
    else:
        timeout_seconds = FULL_SEARCH_TIMEOUT_SECONDS

    async for source_batch in _search_remote_sources_stream(
        sources_db=sources_db,
        keyword=normalized_keyword,
        timeout_seconds=timeout_seconds,
    ):
        if not source_batch:
            continue
        merged_results = _rank_and_dedupe_results(
            normalized_keyword,
            [*merged_results, *source_batch],
        )
        signature = _results_signature(merged_results)
        if signature != last_signature:
            last_signature = signature
            yield merged_results

    _set_cached_results(cache_key, merged_results)


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip().lower()


def _build_dedupe_key(item: SearchResultItem) -> str:
    if item.book_key:
        return item.book_key
    return "|".join(
        [
            _normalize_text(item.name),
            _normalize_text(item.author),
            _normalize_text(item.source_url),
            _normalize_text(item.book_url),
        ]
    )


def _keyword_match_score(keyword: str, item: SearchResultItem) -> float:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return 0.0

    normalized_name = _normalize_text(item.name)
    normalized_author = _normalize_text(item.author)

    score = 0.0
    if normalized_name == normalized_keyword:
        score += 140
    elif normalized_name.startswith(normalized_keyword):
        score += 100
    elif normalized_keyword in normalized_name:
        score += 75

    if normalized_author == normalized_keyword:
        score += 50
    elif normalized_keyword in normalized_author:
        score += 25

    return score


def _source_health_score(source_url: str) -> float:
    state = _SOURCE_HEALTH.get(source_url)
    if not state:
        return 50.0

    score = state.success_rate * 100.0
    score -= min(state.timeout_count * 8.0, 40.0)
    score -= min(state.failure_count * 3.0, 30.0)
    score -= min(state.avg_latency_ms / 90.0, 20.0)
    if state.last_success_at and (time() - state.last_success_at) <= 3600:
        score += 5.0
    return score


def _rank_result_item(keyword: str, item: SearchResultItem) -> float:
    keyword_score = _keyword_match_score(keyword, item)
    source_bonus = _source_health_score(item.source_url) * 0.2
    bookshelf_bonus = 180.0 if item.kind == "bookshelf" else 0.0
    cover_bonus = 3.0 if item.cover_url else 0.0
    chapter_bonus = 2.0 if item.last_chapter else 0.0
    return keyword_score + source_bonus + bookshelf_bonus + cover_bonus + chapter_bonus


def _rank_and_dedupe_results(keyword: str, items: list[SearchResultItem]) -> list[SearchResultItem]:
    best_by_key: dict[str, tuple[float, SearchResultItem]] = {}
    for item in items:
        if not item.book_url or not item.source_url:
            continue
        dedupe_key = _build_dedupe_key(item)
        score = _rank_result_item(keyword, item)
        current = best_by_key.get(dedupe_key)
        if current is None or score > current[0]:
            best_by_key[dedupe_key] = (score, item)

    ranked_items = sorted(
        best_by_key.values(),
        key=lambda pair: (
            -pair[0],
            _normalize_text(pair[1].name),
            _normalize_text(pair[1].author),
            _normalize_text(pair[1].source_name),
        ),
    )
    return [item for _, item in ranked_items]


def _results_signature(items: list[SearchResultItem]) -> tuple[str, ...]:
    return tuple(_build_dedupe_key(item) for item in items)


def _record_source_success(source_url: str, latency_ms: float):
    state = _SOURCE_HEALTH.setdefault(source_url, SourceHealthState())
    _SOURCE_HEALTH.move_to_end(source_url)
    state.success_count += 1
    if state.avg_latency_ms <= 0:
        state.avg_latency_ms = latency_ms
    else:
        state.avg_latency_ms = state.avg_latency_ms * 0.7 + latency_ms * 0.3
    state.last_error = ""
    state.last_success_at = time()
    state.updated_at = time()
    _evict_source_health()


def _record_source_failure(source_url: str, latency_ms: float, error: str, timed_out: bool):
    state = _SOURCE_HEALTH.setdefault(source_url, SourceHealthState())
    _SOURCE_HEALTH.move_to_end(source_url)
    state.failure_count += 1
    if timed_out:
        state.timeout_count += 1
    if state.avg_latency_ms <= 0:
        state.avg_latency_ms = latency_ms
    else:
        state.avg_latency_ms = state.avg_latency_ms * 0.75 + latency_ms * 0.25
    state.last_error = (error or "search-failed")[:200]
    state.updated_at = time()
    _evict_source_health()


def _source_priority_sort_key(source_entry) -> tuple[float, str]:
    health_score = _source_health_score(source_entry.book_source_url)
    return (-health_score, _normalize_text(source_entry.book_source_name))


def _build_search_cache_key(
    keyword: str,
    source_urls: list[str] | None,
    mode: Literal["fast", "full"],
) -> str:
    source_key = "*"
    if source_urls:
        source_key = ",".join(sorted({url.strip() for url in source_urls if url.strip()}))
    return f"{mode}:{source_key}:{_normalize_text(keyword)}"


def _prune_search_cache():
    now = monotonic()
    expired_keys = [key for key, entry in _SEARCH_CACHE.items() if entry.expires_at <= now]
    for key in expired_keys:
        _SEARCH_CACHE.pop(key, None)

    if len(_SEARCH_CACHE) <= MAX_SEARCH_CACHE_ENTRIES:
        return

    oldest_entries = sorted(
        _SEARCH_CACHE.items(),
        key=lambda kv: kv[1].created_at,
    )
    overflow = len(_SEARCH_CACHE) - MAX_SEARCH_CACHE_ENTRIES
    for key, _ in oldest_entries[:overflow]:
        _SEARCH_CACHE.pop(key, None)


def _get_cached_results(cache_key: str) -> list[SearchResultItem]:
    _prune_search_cache()
    entry = _SEARCH_CACHE.get(cache_key)
    if not entry:
        return []
    if entry.expires_at <= monotonic():
        _SEARCH_CACHE.pop(cache_key, None)
        return []
    return list(entry.items)


def _set_cached_results(cache_key: str, items: list[SearchResultItem]):
    _prune_search_cache()
    _SEARCH_CACHE[cache_key] = SearchCacheEntry(
        items=list(items),
        expires_at=monotonic() + SEARCH_CACHE_TTL_SECONDS,
        created_at=monotonic(),
    )


async def _search_remote_sources_stream(
    sources_db,
    keyword: str,
    timeout_seconds: float,
):
    sem = asyncio.Semaphore(max(1, settings.max_concurrent_requests))
    queue: asyncio.Queue[list[SearchResultItem] | None] = asyncio.Queue()

    async def search_and_enqueue(source_db):
        source_url = source_db.book_source_url
        started_at = monotonic()
        try:
            results = await _search_single_source_entry(source_db, keyword, sem)
            latency_ms = (monotonic() - started_at) * 1000
            _record_source_success(source_url, latency_ms)
            if results:
                await queue.put(results)
        except asyncio.CancelledError:
            latency_ms = (monotonic() - started_at) * 1000
            _record_source_failure(source_url, latency_ms, "timeout", timed_out=True)
            raise
        except Exception as exc:
            latency_ms = (monotonic() - started_at) * 1000
            _record_source_failure(source_url, latency_ms, str(exc), timed_out=False)
            logger.warning("Search failed for %s: %s", source_db.book_source_name, exc)

    tasks = [asyncio.create_task(search_and_enqueue(source_db)) for source_db in sources_db]

    async def wait_all_sources():
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Source search timed out after %.1f seconds for keyword=%s",
                timeout_seconds,
                keyword,
            )
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await queue.put(None)

    asyncio.create_task(wait_all_sources())

    while True:
        batch = await queue.get()
        if batch is None:
            break
        yield batch


async def _search_single_source_entry(source_db, keyword: str, sem: asyncio.Semaphore) -> list[SearchResultItem]:
    raw_source = source_db.source_json
    is_tauri = raw_source.strip().startswith("//") or "function search" in raw_source[:500]

    if is_tauri:
        from backend.engine.js_engine import parse_tauri_metadata

        source_meta = parse_tauri_metadata(raw_source)
        source_name = source_meta.get("name", source_db.book_source_name)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            _do_tauri_search,
            raw_source,
            source_db.book_source_url,
            source_name,
            keyword,
        )

    source = BookSourceSchema.model_validate(json.loads(raw_source))
    if not source.searchUrl:
        return []
    return await _search_single_source(source, keyword, sem)


async def _search_bookshelf(keyword: str, limit: int = 20) -> list[SearchResultItem]:
    normalized = keyword.strip()
    if not normalized:
        return []

    like_keyword = f"%{normalized}%"
    startswith_keyword = f"{normalized}%"
    db = await get_db()
    cursor = await db.execute(
        """SELECT
            b.book_key,
            b.name,
            b.author,
            b.cover_url,
            b.intro,
            b.book_url,
            b.source_url,
            b.last_chapter,
            COALESCE(s.book_source_name, '') AS source_name
        FROM books b
        LEFT JOIN book_sources s ON s.book_source_url = b.source_url
        WHERE b.name LIKE ? OR b.author LIKE ?
        ORDER BY
            CASE
                WHEN b.name = ? THEN 0
                WHEN b.name LIKE ? THEN 1
                WHEN b.author = ? THEN 2
                ELSE 3
            END,
            b.updated_at DESC
        LIMIT ?
        """,
        (
            like_keyword,
            like_keyword,
            normalized,
            startswith_keyword,
            normalized,
            limit,
        ),
    )
    rows = await cursor.fetchall()

    return [
        SearchResultItem(
            book_key=row["book_key"] or "",
            name=row["name"],
            author=row["author"] or "",
            cover_url=row["cover_url"] or "",
            intro=row["intro"] or "",
            book_url=row["book_url"],
            source_url=row["source_url"],
            source_name=row["source_name"] or "",
            last_chapter=row["last_chapter"] or "",
            kind="bookshelf",
        )
        for row in rows
    ]


def _do_tauri_search(source_code: str, source_url: str, source_name: str, keyword: str) -> list[SearchResultItem]:
    """Run Tauri source search synchronously (called in executor)."""
    engine = TauriEngine(source_code, source_url)
    raw_results = engine.search(keyword, 1)
    results = []
    for item in raw_results[:20]:
        name = item.get("name") or item.get("title") or ""
        if not name:
            continue
        book_url = make_absolute_url(item.get("bookUrl") or item.get("tocUrl") or "", source_url)
        results.append(SearchResultItem(
            book_key=build_book_key(source_url, book_url),
            name=name,
            author=item.get("author", ""),
            cover_url=item.get("coverUrl", ""),
            intro=item.get("intro", ""),
            book_url=book_url,
            source_url=source_url,
            source_name=source_name,
            last_chapter=item.get("latestChapter") or item.get("lastChapter") or "",
            kind=item.get("kind", ""),
        ))
    return results


async def _search_single_source(
    source: BookSourceSchema,
    keyword: str,
    sem: asyncio.Semaphore,
) -> list[SearchResultItem]:
    async with sem:
        return await _do_search(source, keyword)


async def _do_search(source: BookSourceSchema, keyword: str) -> list[SearchResultItem]:
    parser = RuleParser()

    # Build request
    req = parse_url(source.searchUrl, keyword=keyword, page=1, source_url=source.bookSourceUrl)
    if not req["url"]:
        return []

    # Merge source headers
    headers = parse_headers(source.header)
    headers.update(req["headers"])

    # Fetch
    content = await fetch(
        req["url"],
        method=req["method"],
        headers=headers,
        body=req["body"],
        encoding=req["charset"],
        use_cache=False,
    )

    if not content:
        return []

    # Parse book list
    rule_search = source.ruleSearch
    if not rule_search.bookList:
        return []

    elements = parser.parse_list(rule_search.bookList, content, req["url"])
    if not elements:
        return []

    results = []
    for element in elements[:20]:  # Limit to 20 results per source
        name = parser.parse_element(rule_search.name, element, req["url"])
        if not name:
            continue

        author = _first_str(parser.parse_element(rule_search.author, element, req["url"]))
        cover_url = _first_str(parser.parse_element(rule_search.coverUrl, element, req["url"]))
        cover_url = make_absolute_url(cover_url, req["url"])
        intro = _first_str(parser.parse_element(rule_search.intro, element, req["url"]))
        kind = _first_str(parser.parse_element(rule_search.kind, element, req["url"]))
        last_chapter = _first_str(parser.parse_element(rule_search.lastChapter, element, req["url"]))

        if isinstance(name, list):
            name = name[0] if name else ""

        # Resolve bookUrl — may be a selector OR a template with {{book.field}}
        book_url_rule = rule_search.bookUrl
        if "{{" in book_url_rule and "\n" not in book_url_rule:
            book_url = _resolve_book_url_template(book_url_rule, {
                "name": name,
                "author": author,
                "kind": kind,
                "cover_url": cover_url,
            }, element, parser, req["url"])
        else:
            book_url = _first_str(parser.parse_element(book_url_rule, element, req["url"]))
        book_url = make_absolute_url(book_url, req["url"])

        results.append(SearchResultItem(
            book_key=build_book_key(source.bookSourceUrl, book_url),
            name=name,
            author=author,
            cover_url=cover_url,
            intro=intro,
            book_url=book_url,
            source_url=source.bookSourceUrl,
            source_name=source.bookSourceName,
            last_chapter=last_chapter,
            kind=kind,
        ))

    return results
