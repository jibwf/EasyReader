import json
import pytest
import tempfile
from pathlib import Path

from backend.config import settings
from backend.database import close_db, get_db
from backend.services.audiobook import (
    scan_audiobooks,
    import_audiobook_from_dir,
    import_audiobook_from_zip,
    list_audiobooks,
    delete_audiobook,
    _natural_sort_key,
    _detect_media_type_from_header,
    _needs_transcode,
    _process_media_file,
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


def test_natural_sort_key():
    """Test natural sort handles embedded numbers correctly."""
    items = ["file10.mp3", "file2.mp3", "file1.mp3", "file20.mp3"]
    sorted_items = sorted(items, key=_natural_sort_key)
    assert sorted_items == ["file1.mp3", "file2.mp3", "file10.mp3", "file20.mp3"]


def test_detect_media_type_ftyp():
    """Test MP4 ftyp header is detected as video."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
        f.flush()
        result = _detect_media_type_from_header(Path(f.name))
    assert result == "video"


def test_detect_media_type_non_ftyp():
    """Test non-ftyp header is detected as audio."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x47\x40\x11\x10\x00\x42\xf0\x25" + b"\x00" * 100)
        f.flush()
        result = _detect_media_type_from_header(Path(f.name))
    assert result == "audio"


def test_needs_transcode_returns_false_for_compatible():
    """Test that ffprobe failure returns False (safe default)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
        f.flush()
        result = _needs_transcode(Path(f.name))
    # Fake file won't have valid ffprobe output, but ftyp header means skip
    assert result is False


@pytest.mark.asyncio
async def test_import_audiobook_from_dir_returns_manifest(tmp_path):
    """Test that imported audiobook chapters have correct manifest structure."""
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    _create_test_audiobook_dir(tmp_path, "manifest-structure", [
        ("001 Intro.mp3", b"fake audio"),
        ("002 Chapter.mp4", b"fake video"),
    ])

    await import_audiobook_from_dir("manifest-structure")

    chapters = await get_chapters("local://audiobook/manifest-structure", "local://audiobook")
    assert len(chapters) == 2

    content, content_type = await get_chapter_content(chapters[0].url, "local://audiobook")
    assert content_type == "audiobook"
    manifest = json.loads(content)
    assert "media_files" in manifest
    assert len(manifest["media_files"]) == 1
    assert "filename" in manifest["media_files"][0]
    assert "url" in manifest["media_files"][0]
    assert "media_type" in manifest["media_files"][0]


@pytest.mark.asyncio
async def test_nested_subfolder_import(tmp_path):
    """Test that subfolders within an audiobook are scanned recursively."""
    await close_db()
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"

    # Create nested structure: folder/subfolder/file.mp3
    audiobook_dir = settings.audiobook_dir / "nested-test"
    sub_dir = audiobook_dir / "subfolder"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (audiobook_dir / "root-file.mp3").write_bytes(b"audio1")
    (sub_dir / "nested-file.mp3").write_bytes(b"audio2")

    result = await import_audiobook_from_dir("nested-test")
    assert result is not None
    assert result["chapters"] == 2

    chapters = await get_chapters("local://audiobook/nested-test", "local://audiobook")
    assert len(chapters) == 2
