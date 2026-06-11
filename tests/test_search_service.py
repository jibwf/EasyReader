import asyncio
import json
import pytest
from types import SimpleNamespace

from backend.services import search as search_service
from backend.models.source import BookSourceSchema
from backend.models.book import SearchResultItem
from backend.services.search import _do_search, _rank_and_dedupe_results, search_books_stream, search_books_stream_v2


@pytest.fixture(autouse=True)
def reset_search_runtime_state():
    search_service._SEARCH_CACHE.clear()
    search_service._SOURCE_HEALTH.clear()
    yield
    search_service._SEARCH_CACHE.clear()
    search_service._SOURCE_HEALTH.clear()


@pytest.mark.asyncio
async def test_do_search_parses_legado_html_source(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "测试源",
            "searchUrl": "https://source.example/search?q={{key}}",
            "ruleSearch": {
                "bookList": "@css:article.book",
                "name": "@css:a.title@text",
                "author": "@css:.author@text",
                "coverUrl": "@css:img.cover@src",
                "bookUrl": "@css:a.title@href",
                "intro": "@css:.intro@text",
                "kind": "@css:.kind@text",
                "lastChapter": "@css:.latest@text",
            },
        }
    )
    html = """
    <article class="book">
      <a class="title" href="/book/1">第一本书</a>
      <span class="author">作者甲</span>
      <img class="cover" src="/cover/1.jpg">
      <p class="intro">简介 A</p>
      <span class="kind">玄幻</span>
      <span class="latest">第十章</span>
    </article>
    <article class="book">
      <a class="title" href="https://cdn.example/book/2">第二本书</a>
      <span class="author">作者乙</span>
      <img class="cover" src="//img.example/2.jpg">
      <p class="intro">简介 B</p>
      <span class="kind">科幻</span>
      <span class="latest">第二十章</span>
    </article>
    """
    calls = []

    async def fake_fetch(url, **kwargs):
        calls.append((url, kwargs))
        return html

    monkeypatch.setattr("backend.services.search.fetch", fake_fetch)

    results = await _do_search(source, "三体")

    assert calls[0][0] == "https://source.example/search?q=%E4%B8%89%E4%BD%93"
    assert calls[0][1]["use_cache"] is False
    assert len(results) == 2
    assert results[0].name == "第一本书"
    assert results[0].author == "作者甲"
    assert results[0].cover_url == "https://source.example/cover/1.jpg"
    assert results[0].book_url == "https://source.example/book/1"
    assert results[0].source_name == "测试源"
    assert results[1].cover_url == "https://img.example/2.jpg"
    assert results[1].book_url == "https://cdn.example/book/2"


@pytest.mark.asyncio
async def test_do_search_resolves_book_url_template(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "模板源",
            "searchUrl": "https://source.example/api?q={{key}}",
            "ruleSearch": {
                "bookList": "$.items[*]",
                "name": "$.name",
                "author": "$.author",
                "bookUrl": "/book/{{$.id}}/{{book.name}}",
            },
        }
    )

    async def fake_fetch(*args, **kwargs):
        return '{"items":[{"id":"42","name":"三体","author":"刘慈欣"}]}'

    monkeypatch.setattr("backend.services.search.fetch", fake_fetch)

    results = await _do_search(source, "三体")

    assert len(results) == 1
    assert results[0].book_url == "https://source.example/book/42/三体"
    assert results[0].name == "三体"
    assert results[0].author == "刘慈欣"


@pytest.mark.asyncio
async def test_do_search_uses_rule_parser_for_multiline_book_url_with_result_template(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://bookshelf.example.com",
            "bookSourceName": "多行规则源",
            "searchUrl": "https://bookshelf.example.com/search?q={{key}}",
            "ruleSearch": {
                "bookList": "$.booklist[*]",
                "name": "$.title",
                "author": "$.author",
                "bookUrl": "$.bid\n<js>1100000000 + parseInt(result)</js>\nhttps://bookshelf.example.com/book?id={{result}}",
            },
        }
    )

    async def fake_fetch(*args, **kwargs):
        return '{"booklist":[{"bid":"123","title":"测试书","author":"作者"}]}'

    monkeypatch.setattr("backend.services.search.fetch", fake_fetch)

    results = await _do_search(source, "测试")

    assert len(results) == 1
    assert results[0].book_url == "https://bookshelf.example.com/book?id=1100000123"


@pytest.mark.asyncio
async def test_do_search_uses_first_url_when_book_url_rule_returns_list(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://cards.example.com",
            "bookSourceName": "多链接卡片源",
            "searchUrl": "https://cards.example.com/search?q={{key}}",
            "ruleSearch": {
                "bookList": "@css:.book",
                "name": "@css:.title@text",
                "bookUrl": "@css:a@href",
            },
        }
    )

    async def fake_fetch(*args, **kwargs):
        return """
        <div class="book">
          <a href="/book/1"><img src="/cover.jpg"></a>
          <a class="title" href="/book/1">测试书</a>
          <a href="/book/1/latest">最新章节</a>
        </div>
        """

    monkeypatch.setattr("backend.services.search.fetch", fake_fetch)

    results = await _do_search(source, "测试")

    assert len(results) == 1
    assert results[0].book_url == "https://cards.example.com/book/1"


@pytest.mark.asyncio
async def test_do_search_merges_source_and_request_headers_for_post(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://post.example",
            "bookSourceName": "POST 源",
            "header": '{"Cookie":"sid=abc","User-Agent":"SourceUA"}',
            "searchUrl": (
                'https://post.example/api/search,'
                '{"method":"POST","body":"kw={{key}}&page={{page}}",'
                '"headers":{"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"}}'
            ),
            "ruleSearch": {
                "bookList": "$.items[*]",
                "name": "$.name",
                "author": "$.author",
                "bookUrl": "$.url",
            },
        }
    )
    calls = []

    async def fake_fetch(url, **kwargs):
        calls.append((url, kwargs))
        return '{"items":[{"name":"庆余年","author":"猫腻","url":"/book/qyn"}]}'

    monkeypatch.setattr("backend.services.search.fetch", fake_fetch)

    results = await _do_search(source, "庆余年")

    assert len(results) == 1
    assert calls == [
        (
            "https://post.example/api/search",
            {
                "method": "POST",
                "headers": {
                    "Cookie": "sid=abc",
                    "User-Agent": "SourceUA",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
                "body": "kw=%E5%BA%86%E4%BD%99%E5%B9%B4&page=1",
                "encoding": None,
                "use_cache": False,
            },
        )
    ]
    assert results[0].book_url == "https://post.example/book/qyn"


@pytest.mark.asyncio
async def test_search_books_stream_prefers_bookshelf_results(monkeypatch):
    expected = [
        SearchResultItem(
            name="书架命中",
            author="作者",
            book_url="https://book.example/1",
            source_url="https://source.example",
            source_name="源",
            kind="bookshelf",
        )
    ]

    async def fake_search_bookshelf(keyword: str, limit: int = 20):
        return expected

    async def fake_list_sources(enabled_only: bool = True):
        return []

    monkeypatch.setattr("backend.services.search._search_bookshelf", fake_search_bookshelf)
    monkeypatch.setattr("backend.services.search.list_sources", fake_list_sources)

    batches = [batch async for batch in search_books_stream("测试关键词")]

    assert batches == [expected]


@pytest.mark.asyncio
async def test_search_books_stream_v2_fast_mode_limits_sources(monkeypatch):
    async def fake_search_bookshelf(keyword: str, limit: int = 20):
        return []

    async def fake_list_sources(enabled_only: bool = True):
        return [
            SimpleNamespace(
                source_json=json.dumps(
                    {
                        "bookSourceUrl": f"https://s{i}.example",
                        "bookSourceName": f"源{i}",
                        "searchUrl": f"https://s{i}.example/search?q={{key}}",
                        "ruleSearch": {
                            "bookList": "@css:.book",
                            "name": "@css:.name",
                            "bookUrl": "@css:a@href",
                        },
                    },
                    ensure_ascii=False,
                ),
                book_source_url=f"https://s{i}.example",
                book_source_name=f"源{i}",
            )
            for i in range(10)
        ]

    capture = {"source_count": -1}

    async def fake_remote_stream(sources_db, keyword: str, timeout_seconds: float):
        capture["source_count"] = len(sources_db)
        if False:
            yield []

    monkeypatch.setattr("backend.services.search._search_bookshelf", fake_search_bookshelf)
    monkeypatch.setattr("backend.services.search.list_sources", fake_list_sources)
    monkeypatch.setattr("backend.services.search._search_remote_sources_stream", fake_remote_stream)

    batches = [batch async for batch in search_books_stream_v2("测试关键词", mode="fast")]

    assert batches == []
    assert capture["source_count"] == search_service.FAST_SEARCH_SOURCE_LIMIT


@pytest.mark.asyncio
async def test_search_books_stream_v2_full_mode_uses_all_sources(monkeypatch):
    async def fake_search_bookshelf(keyword: str, limit: int = 20):
        return []

    async def fake_list_sources(enabled_only: bool = True):
        return [
            SimpleNamespace(
                source_json=json.dumps(
                    {
                        "bookSourceUrl": f"https://f{i}.example",
                        "bookSourceName": f"全{i}",
                        "searchUrl": f"https://f{i}.example/search?q={{key}}",
                        "ruleSearch": {
                            "bookList": "@css:.book",
                            "name": "@css:.name",
                            "bookUrl": "@css:a@href",
                        },
                    },
                    ensure_ascii=False,
                ),
                book_source_url=f"https://f{i}.example",
                book_source_name=f"全{i}",
            )
            for i in range(7)
        ]

    capture = {"source_count": -1}

    async def fake_remote_stream(sources_db, keyword: str, timeout_seconds: float):
        capture["source_count"] = len(sources_db)
        if False:
            yield []

    monkeypatch.setattr("backend.services.search._search_bookshelf", fake_search_bookshelf)
    monkeypatch.setattr("backend.services.search.list_sources", fake_list_sources)
    monkeypatch.setattr("backend.services.search._search_remote_sources_stream", fake_remote_stream)

    batches = [batch async for batch in search_books_stream_v2("测试关键词", mode="full")]

    assert batches == []
    assert capture["source_count"] == 7


@pytest.mark.asyncio
async def test_search_books_stream_v2_fast_mode_uses_cache(monkeypatch):
    async def fake_search_bookshelf(keyword: str, limit: int = 20):
        return []

    async def fake_list_sources(enabled_only: bool = True):
        return [
            SimpleNamespace(
                source_json='{"bookSourceUrl":"https://cache.example","bookSourceName":"缓存源","searchUrl":"https://cache.example/search?q={{key}}","ruleSearch":{"bookList":"@css:.book","name":"@css:.name","bookUrl":"@css:a@href"}}',
                book_source_url="https://cache.example",
                book_source_name="缓存源",
            )
        ]

    calls = {"remote": 0}

    async def fake_remote_stream(sources_db, keyword: str, timeout_seconds: float):
        calls["remote"] += 1
        yield [
            SearchResultItem(
                book_key="bk_cache",
                name="缓存结果",
                author="作者",
                book_url="https://cache.example/book/1",
                source_url="https://cache.example",
                source_name="缓存源",
            )
        ]

    monkeypatch.setattr("backend.services.search._search_bookshelf", fake_search_bookshelf)
    monkeypatch.setattr("backend.services.search.list_sources", fake_list_sources)
    monkeypatch.setattr("backend.services.search._search_remote_sources_stream", fake_remote_stream)

    first_batches = [batch async for batch in search_books_stream_v2("缓存关键词", mode="fast")]
    second_batches = [batch async for batch in search_books_stream_v2("缓存关键词", mode="fast")]

    assert calls["remote"] == 1
    assert first_batches
    assert second_batches
    assert first_batches[-1][0].name == "缓存结果"
    assert second_batches[-1][0].name == "缓存结果"


def test_rank_and_dedupe_prefers_higher_scored_duplicate():
    items = [
        SearchResultItem(
            book_key="bk_dup",
            name="三体",
            author="刘慈欣",
            book_url="https://book.example/1",
            source_url="https://source.example",
            source_name="普通源",
            kind="",
        ),
        SearchResultItem(
            book_key="bk_dup",
            name="三体",
            author="刘慈欣",
            book_url="https://book.example/1",
            source_url="https://source.example",
            source_name="书架",
            kind="bookshelf",
        ),
    ]

    ranked = _rank_and_dedupe_results("三体", items)

    assert len(ranked) == 1
    assert ranked[0].kind == "bookshelf"


@pytest.mark.asyncio
async def test_search_books_stream_source_timeout(monkeypatch):
    async def fake_search_bookshelf(keyword: str, limit: int = 20):
        return []

    async def fake_list_sources(enabled_only: bool = True):
        return [
            SimpleNamespace(
                source_json='{"bookSourceUrl":"https://s.example","bookSourceName":"源A","searchUrl":"https://s.example/search?q={{key}}","ruleSearch":{"bookList":"@css:.book","name":"@css:.name","bookUrl":"@css:a@href"}}',
                book_source_url="https://s.example",
                book_source_name="源A",
            )
        ]

    async def slow_do_search(source, keyword: str):
        await asyncio.sleep(0.05)
        return [
            SearchResultItem(
                name="慢结果",
                book_url="https://book.example/slow",
                source_url=source.bookSourceUrl,
            )
        ]

    monkeypatch.setattr("backend.services.search._search_bookshelf", fake_search_bookshelf)
    monkeypatch.setattr("backend.services.search.list_sources", fake_list_sources)
    monkeypatch.setattr("backend.services.search._do_search", slow_do_search)

    original_wait_for = asyncio.wait_for

    async def fast_timeout(awaitable, timeout):
        return await original_wait_for(awaitable, 0.01)

    monkeypatch.setattr("backend.services.search.asyncio.wait_for", fast_timeout)

    batches = [batch async for batch in search_books_stream("超时关键词")]

    assert batches == []
