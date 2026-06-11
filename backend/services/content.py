"""Content service — fetch book info, chapter list, and chapter content."""

import base64
import json
import logging
import re as _re

from backend.engine.parser import RuleParser
from backend.engine.fetcher import fetch, parse_headers
from backend.engine.url_parser import make_absolute_url
from backend.models.source import BookSourceSchema, BookInfoRule
from backend.models.book import BookSchema, ChapterSchema
from backend.services.source_manager import get_source, get_source_raw
from backend.engine.js_engine import TauriEngine
from backend.database import get_db
from backend.utils.book_key import build_book_key

logger = logging.getLogger(__name__)


def _parse_book_fields(parser: RuleParser, rule_info: BookInfoRule, content: str | dict, base_url: str) -> dict[str, str]:
    """Extract book info fields from content for template resolution."""
    fields = {}
    for field_name, rule in [
        ("name", rule_info.name),
        ("author", rule_info.author),
        ("kind", rule_info.kind),
        ("coverUrl", rule_info.coverUrl),
        ("lastChapter", rule_info.lastChapter),
    ]:
        if rule and "{{" not in rule:
            val = parser.parse(rule, content, base_url)
            if isinstance(val, list):
                val = val[0] if val else ""
            fields[field_name] = val or ""
    return fields


def _resolve_template(template: str, fields: dict[str, str]) -> str:
    """Resolve {{book.field}} in URL templates."""
    def replacer(m: _re.Match) -> str:
        expr = m.group(1)
        if expr.startswith("book."):
            return fields.get(expr[5:], "")
        return ""
    return _re.sub(r"\{\{(.+?)\}\}", replacer, template)


def _element_attr(element, attr: str) -> str:
    """Read an attribute from BeautifulSoup/lxml-like elements."""
    if not hasattr(element, "get"):
        return ""
    try:
        value = element.get(attr, "")
    except TypeError:
        value = element.get(attr)
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _element_or_parent_attr(element, attr: str) -> str:
    value = _element_attr(element, attr)
    if value:
        return value
    parent = getattr(element, "parent", None)
    return _element_attr(parent, attr) if parent is not None else ""


def _data_gdx_values(element) -> list[str]:
    if not hasattr(element, "attrs"):
        return []
    attrs = getattr(element, "attrs", {}) or {}
    values = []
    for key, value in attrs.items():
        if not str(key).startswith("data-gdx"):
            continue
        if isinstance(value, list):
            values.extend(str(v) for v in value if v)
        elif value:
            values.append(str(value))
    return values


def _sort_toc_elements(elements: list) -> list:
    keyed = []
    for index, element in enumerate(elements):
        value = _element_or_parent_attr(element, "data-gdx7")
        if not value.isdigit():
            return elements
        keyed.append((int(value), index, element))
    keyed.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in keyed]


def _looks_like_placeholder_chapter(title: str) -> bool:
    return bool(_re.fullmatch(r"chapter\s*\d+", (title or "").strip(), flags=_re.IGNORECASE))


def _decode_base64_url(value: str) -> str:
    if not value:
        return ""
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _find_data_gdx_title(element) -> str:
    for value in _data_gdx_values(element):
        decoded = _decode_base64_url(value)
        if decoded.startswith(("/", "http://", "https://")):
            continue
        if value and not _looks_like_placeholder_chapter(value):
            return value.strip()
    return ""


def _find_data_gdx_url(element) -> str:
    for value in _data_gdx_values(element):
        decoded = _decode_base64_url(value)
        if decoded.startswith(("/", "http://", "https://")):
            return decoded
    return ""


def _normalize_chapter_entry(title, url, element, base_url: str) -> tuple[str, str]:
    """Apply source-agnostic fallbacks for obfuscated chapter anchors."""
    if isinstance(title, list):
        title = title[0] if title else ""
    if not isinstance(title, str):
        title = str(title or "")
    if not isinstance(url, str):
        url = ""

    original_title_is_placeholder = _looks_like_placeholder_chapter(title)
    fallback_title = _element_attr(element, "data-gdx3") or _find_data_gdx_title(element)
    if fallback_title and (not title or original_title_is_placeholder):
        title = fallback_title

    absolute_url = make_absolute_url(url, base_url)
    encoded_url = _element_attr(element, "data-gdx1")
    decoded_url = _decode_base64_url(encoded_url) or _find_data_gdx_url(element)
    if decoded_url:
        decoded_absolute_url = make_absolute_url(decoded_url, base_url)
        if encoded_url or not absolute_url or absolute_url.rstrip("/") == base_url.rstrip("/") or original_title_is_placeholder:
            absolute_url = decoded_absolute_url

    return title.strip(), absolute_url


async def get_book_info(book_url: str, source_url: str) -> BookSchema | None:
    """Fetch and parse book details from a book URL."""
    if source_url.startswith("local://"):
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM books WHERE book_url = ? AND source_url = ?",
            (book_url, source_url),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return BookSchema(
            id=row["id"],
            book_key=row["book_key"] or "",
            name=row["name"],
            author=row["author"] or "",
            cover_url=row["cover_url"] or "",
            intro=row["intro"] or "",
            book_url=row["book_url"],
            source_url=row["source_url"],
            category_name=row["category_name"] or "网文",
            last_chapter=row["last_chapter"] or "",
            total_chapters=row["total_chapters"] or 0,
            added_at=row["added_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    source = await get_source(source_url)
    if not source:
        return None

    parser = RuleParser()
    headers = parse_headers(source.header)

    content = await fetch(book_url, headers=headers)
    if not content:
        return None

    rule_info = source.ruleBookInfo
    name = parser.parse(rule_info.name, content, book_url)
    author = parser.parse(rule_info.author, content, book_url)
    cover_url = parser.parse(rule_info.coverUrl, content, book_url)
    cover_url = make_absolute_url(cover_url if isinstance(cover_url, str) else "", book_url)
    intro = parser.parse(rule_info.intro, content, book_url)

    if isinstance(name, list):
        name = name[0] if name else ""
    if isinstance(author, list):
        author = author[0] if author else ""
    if isinstance(intro, list):
        intro = "\n".join(intro)

    return BookSchema(
        book_key=build_book_key(source_url, book_url),
        name=name or "",
        author=author or "",
        cover_url=cover_url,
        intro=intro or "",
        book_url=book_url,
        source_url=source_url,
    )


async def get_chapters(book_url: str, source_url: str) -> list[ChapterSchema]:
    """Fetch and parse chapter list (TOC) for a book."""
    if source_url.startswith("local://"):
        db = await get_db()
        cursor = await db.execute(
            "SELECT id, book_key FROM books WHERE book_url = ? AND source_url = ?",
            (book_url, source_url),
        )
        book_row = await cursor.fetchone()
        if not book_row:
            return []

        book_key = book_row["book_key"] or ""

        chapter_cursor = await db.execute(
            "SELECT * FROM chapters WHERE book_id = ? ORDER BY idx ASC",
            (book_row["id"],),
        )
        rows = await chapter_cursor.fetchall()
        return [
            ChapterSchema(
                id=row["id"],
                book_id=row["book_id"],
                book_key=book_key,
                title=row["title"],
                url=row["url"],
                idx=row["idx"],
                cached=bool(row["cached"]),
            )
            for row in rows
        ]

    raw = await get_source_raw(source_url)
    if raw and raw[1] == "tauri":
        return await _get_chapters_tauri(raw[0], source_url, book_url)

    source = await get_source(source_url)
    if not source:
        return []

    parser = RuleParser()
    headers = parse_headers(source.header)

    # Fetch book info page
    rule_info = source.ruleBookInfo
    content = await fetch(book_url, headers=headers)
    if not content:
        return []

    # Parse book fields needed for template resolution
    book_fields = _parse_book_fields(parser, rule_info, content, book_url)

    # Determine TOC URL
    toc_url = book_url
    if rule_info.tocUrl:
        toc_url_rule = rule_info.tocUrl
        if "{{" in toc_url_rule:
            toc_url = _resolve_template(toc_url_rule, book_fields)
        else:
            parsed_toc_url = parser.parse(toc_url_rule, content, book_url)
            if parsed_toc_url and isinstance(parsed_toc_url, str):
                toc_url = parsed_toc_url
        toc_url = make_absolute_url(toc_url, book_url)
        if toc_url != book_url:
            content = await fetch(toc_url, headers=headers)
            if not content:
                return []

    rule_toc = source.ruleToc
    if not rule_toc.chapterList:
        return []

    elements = _sort_toc_elements(parser.parse_list(rule_toc.chapterList, content, toc_url))
    if not elements:
        return []

    book_key = build_book_key(source_url, book_url)

    chapters = []
    for idx, element in enumerate(elements):
        title = parser.parse_element(rule_toc.chapterName, element, toc_url)
        url = parser.parse_element(rule_toc.chapterUrl, element, toc_url)
        title, url = _normalize_chapter_entry(title, url, element, toc_url)

        if not title:
            continue

        chapters.append(ChapterSchema(
            book_id=0,
            book_key=book_key,
            title=title,
            url=url,
            idx=idx,
        ))

    # Handle multi-page TOC
    if rule_toc.nextTocUrl:
        next_url = parser.parse(rule_toc.nextTocUrl, content, toc_url)
        if next_url and isinstance(next_url, str):
            next_url = make_absolute_url(next_url, toc_url)
            more = await _fetch_next_toc(source, next_url, headers, len(chapters), book_key)
            chapters.extend(more)

    return chapters


async def _fetch_next_toc(
    source: BookSourceSchema,
    url: str,
    headers: dict,
    start_idx: int,
    book_key: str,
    max_pages: int = 10,
) -> list[ChapterSchema]:
    """Follow pagination for multi-page TOCs."""
    parser = RuleParser()
    rule_toc = source.ruleToc
    chapters = []

    for _ in range(max_pages):
        content = await fetch(url, headers=headers)
        if not content:
            break

        elements = _sort_toc_elements(parser.parse_list(rule_toc.chapterList, content, url))
        if not elements:
            break

        for element in elements:
            title = parser.parse_element(rule_toc.chapterName, element, url)
            ch_url = parser.parse_element(rule_toc.chapterUrl, element, url)
            title, ch_url = _normalize_chapter_entry(title, ch_url, element, url)
            if not title:
                continue

            chapters.append(ChapterSchema(
                book_id=0,
                book_key=book_key,
                title=title,
                url=ch_url,
                idx=start_idx + len(chapters),
            ))

        next_url = parser.parse(rule_toc.nextTocUrl, content, url)
        if not next_url or not isinstance(next_url, str) or next_url == url:
            break
        url = make_absolute_url(next_url, url)

    return chapters


async def get_chapter_content(
    chapter_url: str,
    source_url: str,
) -> str:
    """Fetch and parse chapter text content."""
    if source_url.startswith("local://"):
        db = await get_db()
        cursor = await db.execute(
            "SELECT content FROM chapter_cache WHERE chapter_url = ? ORDER BY id DESC LIMIT 1",
            (chapter_url,),
        )
        row = await cursor.fetchone()
        return row["content"] if row else ""

    raw = await get_source_raw(source_url)
    if raw and raw[1] == "tauri":
        text = await _get_chapter_content_tauri(raw[0], source_url, chapter_url)
        if text:
            return text
        return await _get_cached_chapter_content(chapter_url)

    source = await get_source(source_url)
    if not source:
        return ""

    parser = RuleParser()
    headers = parse_headers(source.header)
    rule_content = source.ruleContent

    if not rule_content.content:
        return ""

    content = await fetch(chapter_url, headers=headers)
    if not content:
        return await _get_cached_chapter_content(chapter_url)

    text = parser.parse(rule_content.content, content, chapter_url)
    if isinstance(text, list):
        text = "\n".join(text)

    # Handle multi-page content
    if rule_content.nextContentUrl:
        next_url = parser.parse(rule_content.nextContentUrl, content, chapter_url)
        if next_url and isinstance(next_url, str):
            next_url = make_absolute_url(next_url, chapter_url)
            more = await _fetch_next_content(source, next_url, headers)
            if more:
                text = text + "\n" + more

    # Apply replacement regex
    if rule_content.replaceRegex and text:
        import re
        try:
            text = re.sub(rule_content.replaceRegex, "", text)
        except re.error:
            pass

    # Clean up
    text = _clean_content(text)
    if text:
        return text
    return await _get_cached_chapter_content(chapter_url)


async def _get_cached_chapter_content(chapter_url: str) -> str:
    db = await get_db()
    cursor = await db.execute(
        """SELECT content FROM chapter_cache
        WHERE chapter_url = ? OR rtrim(chapter_url, '/') = rtrim(?, '/')
        ORDER BY id DESC
        LIMIT 1""",
        (chapter_url, chapter_url),
    )
    row = await cursor.fetchone()
    return row["content"] if row else ""


async def _fetch_next_content(
    source: BookSourceSchema,
    url: str,
    headers: dict,
    max_pages: int = 10,
) -> str:
    """Follow pagination for multi-page chapter content."""
    parser = RuleParser()
    rule_content = source.ruleContent
    parts = []

    for _ in range(max_pages):
        content = await fetch(url, headers=headers)
        if not content:
            break

        text = parser.parse(rule_content.content, content, url)
        if isinstance(text, list):
            text = "\n".join(text)
        if not text:
            break
        parts.append(text)

        next_url = parser.parse(rule_content.nextContentUrl, content, url)
        if not next_url or not isinstance(next_url, str) or next_url == url:
            break
        url = make_absolute_url(next_url, url)

    return "\n".join(parts)


def _clean_content(text: str) -> str:
    if not text:
        return ""
    import re
    # Convert <br>, <br/>, <p> tags to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    import html
    text = html.unescape(text)
    # Clean up whitespace
    lines = text.split("\n")
    lines = [line.strip() for line in lines]
    # Remove empty lines at start/end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    # Collapse multiple empty lines
    result = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                result.append("")
            prev_empty = True
        else:
            result.append(line)
            prev_empty = False
    return "\n".join(result)


# --- Tauri engine helpers ---

async def _get_chapters_tauri(source_code: str, source_url: str, book_url: str) -> list[ChapterSchema]:
    """Get chapters using Tauri JS engine."""
    import asyncio
    loop = asyncio.get_event_loop()

    def run():
        engine = TauriEngine(source_code, source_url)
        return engine.chapter_list(book_url)

    raw = await loop.run_in_executor(None, run)
    chapters = []
    for idx, item in enumerate(raw):
        title = item.get("title") or item.get("name") or ""
        url = item.get("url") or item.get("chapterUrl") or ""
        if not title:
            continue
        chapters.append(ChapterSchema(
            book_id=0,
            title=title,
            url=url,
            idx=idx,
        ))
    return chapters


async def _get_chapter_content_tauri(source_code: str, source_url: str, chapter_url: str) -> str:
    """Get chapter content using Tauri JS engine."""
    import asyncio
    loop = asyncio.get_event_loop()

    def run():
        engine = TauriEngine(source_code, source_url)
        return engine.chapter_content(chapter_url)

    return await loop.run_in_executor(None, run)
