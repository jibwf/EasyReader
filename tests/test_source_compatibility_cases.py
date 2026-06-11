import pytest

from backend.engine.js_engine import TauriEngine, parse_tauri_metadata
from backend.models.source import BookSourceSchema
from backend.services.content import get_chapter_content, get_chapters
from backend.services.search import _do_search, _do_tauri_search
from tests.fixtures.source_cases import (
    HTML_CSS_CASE,
    JSON_API_CASE,
    JSON_MANGA_CASE,
    TAURI_SOURCE,
    XPATH_RELATIVE_CASE,
)


LEGADO_CASES = [HTML_CSS_CASE, JSON_API_CASE, JSON_MANGA_CASE, XPATH_RELATIVE_CASE]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", LEGADO_CASES, ids=[case["name"] for case in LEGADO_CASES])
async def test_legado_compatibility_cases_cover_search_toc_and_content(case, monkeypatch):
    source = BookSourceSchema.model_validate(case["source"])

    async def fake_search_fetch(url, **kwargs):
        return case["search_response"]

    monkeypatch.setattr("backend.services.search.fetch", fake_search_fetch)

    results = await _do_search(source, "测试")

    assert len(results) == 1
    assert results[0].name == case["expected"]["search_name"]
    assert results[0].author == case["expected"]["search_author"]
    assert results[0].book_url == case["book_url"]

    async def fake_get_source_raw(source_url):
        return None

    async def fake_get_source(source_url):
        return source

    async def fake_content_fetch(url, **kwargs):
        if url == case["book_url"]:
            return case["toc_response"]
        return case["content_responses"].get(url, "")

    monkeypatch.setattr("backend.services.content.get_source_raw", fake_get_source_raw)
    monkeypatch.setattr("backend.services.content.get_source", fake_get_source)
    monkeypatch.setattr("backend.services.content.fetch", fake_content_fetch)

    chapters = await get_chapters(case["book_url"], source.bookSourceUrl)
    content = await get_chapter_content(case["chapter_url"], source.bookSourceUrl)

    assert [chapter.title for chapter in chapters] == case["expected"]["chapter_titles"]
    assert content == case["expected"]["content"]


def test_tauri_compatibility_case_covers_search_metadata_toc_and_content():
    meta = parse_tauri_metadata(TAURI_SOURCE)

    assert meta["name"] == "Tauri 漫画源"
    assert meta["url"] == "https://tauri.example"
    assert meta["type"] == "comic"

    results = _do_tauri_search(TAURI_SOURCE, meta["url"], meta["name"], "测试")
    assert len(results) == 1
    assert results[0].name == "测试 漫画"
    assert results[0].book_url == "https://tauri.example/book/1"

    engine = TauriEngine(TAURI_SOURCE, meta["url"])

    assert [chapter["title"] for chapter in engine.chapter_list("https://tauri.example/book/1")] == ["第 1 话", "第 2 话"]
    assert engine.chapter_content("https://tauri.example/chapter/1") == '["https://tauri.example/images/1.jpg", "https://tauri.example/images/2.jpg"]'
