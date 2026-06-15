import pytest

from backend.config import settings
from backend.database import close_db, get_db
from backend.models.source import BookSourceSchema
from backend.services.content import get_chapter_content, get_chapters
from backend.utils.book_key import build_book_key


@pytest.mark.asyncio
async def test_get_chapters_parses_toc_from_book_page(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "目录源",
            "ruleBookInfo": {},
            "ruleToc": {
                "chapterList": "@css:ul.toc li",
                "chapterName": "@css:a@text",
                "chapterUrl": "@css:a@href",
            },
        }
    )
    html = """
    <ul class="toc">
      <li><a href="/book/1/chapter/1.html">第一章 起点</a></li>
      <li><a href="chapter/2.html">第二章 继续</a></li>
    </ul>
    """

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(html))

    chapters = await get_chapters("https://source.example/book/1/index.html", "https://source.example")

    assert [chapter.title for chapter in chapters] == ["第一章 起点", "第二章 继续"]
    assert [chapter.idx for chapter in chapters] == [0, 1]
    assert chapters[0].url == "https://source.example/book/1/chapter/1.html"
    assert chapters[1].url == "https://source.example/book/1/chapter/2.html"


@pytest.mark.asyncio
async def test_get_chapters_uses_toc_url_template_and_fetches_toc_page(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "独立目录源",
            "ruleBookInfo": {
                "name": "@css:h1@text",
                "tocUrl": "/toc/{{book.name}}.html",
            },
            "ruleToc": {
                "chapterList": "@css:.chapter",
                "chapterName": "@css:a@text",
                "chapterUrl": "@css:a@href",
            },
        }
    )
    book_page = "<h1>三体</h1>"
    toc_page = '<div class="chapter"><a href="/c/1.html">第一章</a></div>'
    fetched_urls = []

    async def fake_fetch(url, **kwargs):
        fetched_urls.append(url)
        return book_page if url.endswith("/book/1") else toc_page

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", fake_fetch)

    chapters = await get_chapters("https://source.example/book/1", "https://source.example")

    assert fetched_urls == ["https://source.example/book/1", "https://source.example/toc/三体.html"]
    assert len(chapters) == 1
    assert chapters[0].title == "第一章"
    assert chapters[0].url == "https://source.example/c/1.html"


@pytest.mark.asyncio
async def test_get_chapters_uses_data_gdx_fallback_for_placeholder_titles(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://www.360lele.cc",
            "bookSourceName": "乐乐小说",
            "ruleBookInfo": {},
            "ruleToc": {
                "chapterList": "@css:ol li a",
                "chapterName": "text",
                "chapterUrl": "href",
            },
        }
    )
    html = """
    <ol>
      <li>
        <a href="/book/46690/" class="g" data-gdx3="分卷阅读1"
           data-gdx1="L2Jvb2svNDY2OTAvOTI1MTE4Lmh0bWw=">Chapter 01</a>
      </li>
    </ol>
    """

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(html))

    chapters = await get_chapters("https://www.360lele.cc/book/46690/", "https://www.360lele.cc")

    assert len(chapters) == 1
    assert chapters[0].title == "分卷阅读1"
    assert chapters[0].url == "https://www.360lele.cc/book/46690/925118.html"


@pytest.mark.asyncio
async def test_get_chapters_scans_numbered_data_gdx_attributes(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://www.360lele.cc",
            "bookSourceName": "乐乐小说",
            "ruleBookInfo": {},
            "ruleToc": {
                "chapterList": "@css:ol li a",
                "chapterName": "text",
                "chapterUrl": "href",
            },
        }
    )
    html = """
    <ol>
      <li>
        <a href="/book/32935/" class="g" data-gdx8="分卷阅读25"
           data-gdx9="L2Jvb2svMzI5MzUvODM5MjMwLmh0bWw=">Chapter 01</a>
      </li>
    </ol>
    """

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(html))

    chapters = await get_chapters("https://www.360lele.cc/book/32935/", "https://www.360lele.cc")

    assert len(chapters) == 1
    assert chapters[0].title == "分卷阅读25"
    assert chapters[0].url == "https://www.360lele.cc/book/32935/839230.html"


@pytest.mark.asyncio
async def test_get_chapters_sorts_obfuscated_data_gdx_catalog(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://www.360lele.cc",
            "bookSourceName": "乐乐小说",
            "ruleBookInfo": {},
            "ruleToc": {
                "chapterList": "@css:ol li a",
                "chapterName": "text",
                "chapterUrl": "href",
            },
        }
    )
    html = """
    <ol>
      <li data-gdx7="24">
        <a href="/book/32935/" class="g" data-gdx8="分卷阅读25"
           data-gdx9="L2Jvb2svMzI5MzUvODM5MjMwLmh0bWw=">Chapter 01</a>
      </li>
      <li data-gdx7="0">
        <a href="/book/32935/" class="g" data-gdx8="分卷阅读1"
           data-gdx9="L2Jvb2svMzI5MzUvODM5MjA2Lmh0bWw=">Chapter 96</a>
      </li>
      <li data-gdx7="1">
        <a href="/book/32935/" class="g" data-gdx8="分卷阅读2"
           data-gdx9="L2Jvb2svMzI5MzUvODM5MjA3Lmh0bWw=">Chapter 54</a>
      </li>
    </ol>
    """

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(html))

    chapters = await get_chapters("https://www.360lele.cc/book/32935/", "https://www.360lele.cc")

    assert [chapter.title for chapter in chapters] == ["分卷阅读1", "分卷阅读2", "分卷阅读25"]
    assert [chapter.idx for chapter in chapters] == [0, 1, 2]
    assert chapters[0].url == "https://www.360lele.cc/book/32935/839206.html"


@pytest.mark.asyncio
async def test_get_chapter_content_parses_cleans_and_applies_replacement(monkeypatch):
    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "正文源",
            "ruleContent": {
                "content": "@css:div.content@html",
                "replaceRegex": "广告.*",
            },
        }
    )
    html = """
    <div class="content">
      <p>第一段&nbsp;正文</p>
      <p>广告 请下载 App</p>
      <p>第二段正文</p>
    </div>
    """

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(html))

    content, _ = await get_chapter_content("https://source.example/c/1.html", "https://source.example")

    assert "广告" not in content
    assert content == "第一段\u00a0正文\n\n第二段正文"


@pytest.mark.asyncio
async def test_get_chapter_content_falls_back_to_server_cache_when_fetch_fails(tmp_path, monkeypatch):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"

    db = await get_db()
    source_url = "https://source.example"
    book_url = "https://source.example/book/1"
    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url, total_chapters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (build_book_key(source_url, book_url), "Cache Book", "", "", "", book_url, source_url, 1),
    )
    cursor = await db.execute(
        "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
        (book_url, source_url),
    )
    row = await cursor.fetchone()
    book_id = row["id"]
    await db.execute(
        """INSERT INTO chapter_cache
        (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
        VALUES (?, ?, ?, ?, ?, 'novel')""",
        (book_id, 0, "第一章", "https://source.example/c/1.html", "server cached chapter"),
    )
    await db.commit()

    source = BookSourceSchema.model_validate(
        {
            "bookSourceUrl": "https://source.example",
            "bookSourceName": "正文源",
            "ruleContent": {
                "content": "@css:div.content@html",
            },
        }
    )

    monkeypatch.setattr("backend.services.content.get_source_raw", lambda source_url: _async_value(None))
    monkeypatch.setattr("backend.services.content.get_source", lambda source_url: _async_value(source))
    monkeypatch.setattr("backend.services.content.fetch", lambda url, **kwargs: _async_value(""))

    content, _ = await get_chapter_content("https://source.example/c/1.html/", "https://source.example")

    assert content == "server cached chapter"

    await close_db()


async def _async_value(value):
    return value
