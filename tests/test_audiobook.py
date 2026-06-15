import json
import pytest

from backend.config import settings
from backend.database import close_db, get_db
from backend.services.audiobook import (
    scan_audiobooks,
    import_audiobook_from_dir,
    import_audiobook_from_zip,
    list_audiobooks,
    delete_audiobook,
)
from backend.services.content import get_chapters, get_chapter_content


def _create_test_audiobook_dir(tmp_path, folder_name: str, files: list[tuple[str, bytes]]):
    audiobook_dir = settings.audiobook_dir / folder_name
    audiobook_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files:
        (audiobook_dir / name).write_bytes(content)
    return audiobook_dir


@pytest.mark.asyncio
async def test_import_audiobook_from_dir(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "test-book", [
        ("001 Intro.mp3", b"fake audio"),
        ("002 Chapter 1.mp4", b"fake video"),
        ("003 Chapter 2.mp3", b"fake audio"),
    ])

    result = await import_audiobook_from_dir("test-book")
    assert result is not None
    assert result["book_id"] > 0
    assert result["chapters"] == 3
    assert result["name"] == "test-book"

    chapters = await get_chapters("local://audiobook/test-book", "local://audiobook")
    assert len(chapters) == 3
    assert chapters[0].title == "001 Intro"
    assert chapters[1].title == "002 Chapter 1"
    assert chapters[2].title == "003 Chapter 2"


@pytest.mark.asyncio
async def test_audiobook_chapter_content_returns_manifest(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "manifest-test", [
        ("001 Intro.mp3", b"fake audio"),
    ])

    await import_audiobook_from_dir("manifest-test")

    chapters = await get_chapters("local://audiobook/manifest-test", "local://audiobook")
    assert len(chapters) == 1

    content, content_type = await get_chapter_content(chapters[0].url, "local://audiobook")
    assert content_type == "audiobook"
    manifest = json.loads(content)
    assert "media_files" in manifest
    assert len(manifest["media_files"]) == 1
    assert manifest["media_files"][0]["media_type"] == "audio"
    assert manifest["media_files"][0]["filename"] == "001 Intro.mp3"


@pytest.mark.asyncio
async def test_scan_audiobooks_imports_new_folder(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "scan-test", [
        ("001 Intro.mp3", b"fake audio"),
    ])

    result = await scan_audiobooks()
    assert result["imported"] == 1
    assert result["scanned"] == 1


@pytest.mark.asyncio
async def test_scan_skips_already_imported(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "skip-test", [
        ("001 Intro.mp3", b"fake audio"),
    ])

    await scan_audiobooks()
    result = await scan_audiobooks()
    assert result["skipped"] == 1
    assert result["imported"] == 0


@pytest.mark.asyncio
async def test_list_audiobooks(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "list-test", [
        ("001 Intro.mp3", b"fake audio"),
    ])
    await import_audiobook_from_dir("list-test")

    books = await list_audiobooks()
    assert len(books) == 1
    assert books[0].name == "list-test"
    assert books[0].media_root == "list-test"


@pytest.mark.asyncio
async def test_delete_audiobook(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "delete-test", [
        ("001 Intro.mp3", b"fake audio"),
    ])
    result = await import_audiobook_from_dir("delete-test")
    book_id = result["book_id"]

    deleted = await delete_audiobook(book_id)
    assert deleted is True

    books = await list_audiobooks()
    assert len(books) == 0


@pytest.mark.asyncio
async def test_import_audiobook_from_zip(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr("001 Intro.mp3", b"fake audio")
        zf.writestr("002 Chapter 1.mp4", b"fake video")
    zip_content = buf.getvalue()

    result = await import_audiobook_from_zip("test.zip", zip_content)
    assert result["book_id"] > 0
    assert result["chapters"] == 2


@pytest.mark.asyncio
async def test_empty_folder_returns_none(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    audiobook_dir = settings.audiobook_dir / "empty"
    audiobook_dir.mkdir(parents=True, exist_ok=True)

    result = await import_audiobook_from_dir("empty")
    assert result is None


@pytest.mark.asyncio
async def test_natural_sort_order(tmp_path):
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "sort-test", [
        ("010 Chapter 10.mp3", b"fake"),
        ("002 Chapter 2.mp3", b"fake"),
        ("001 Chapter 1.mp3", b"fake"),
        ("003 Chapter 3.mp3", b"fake"),
    ])

    await import_audiobook_from_dir("sort-test")

    chapters = await get_chapters("local://audiobook/sort-test", "local://audiobook")
    assert len(chapters) == 4
    assert chapters[0].title == "001 Chapter 1"
    assert chapters[1].title == "002 Chapter 2"
    assert chapters[2].title == "003 Chapter 3"
    assert chapters[3].title == "010 Chapter 10"
