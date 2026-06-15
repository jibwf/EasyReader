"""Audiobook service — scan, import, and manage audiobooks."""

import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote

from backend.config import settings
from backend.database import get_db
from backend.models.book import BookSchema
from backend.utils.book_key import build_book_key

AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.ogg', '.flac'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv'}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

AUDIobook_SOURCE_URL = "local://audiobook"


def _natural_sort_key(s: str):
    """Sort strings with embedded numbers naturally."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def _media_type_from_ext(ext: str) -> str:
    return "video" if ext.lower() in VIDEO_EXTENSIONS else "audio"


def _detect_media_type(file_path: Path) -> str:
    """Detect actual media type by reading file header bytes."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        if len(header) < 4:
            return "audio"
        # MP4/MOV container: starts with box size + 'ftyp'
        if header[4:8] == b"ftyp":
            return "video"
        # AAC ADTS frame: starts with 0xFF 0xF1 or 0xFF 0xF9 or 0xFF 0xF3
        if header[0] == 0xFF and (header[1] & 0xF0) in (0xF0, 0xE0):
            return "audio"
        # MP3: starts with ID3 tag or sync word
        if header[:3] == b"ID3" or (header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
            return "audio"
        # OGG: starts with 'OggS'
        if header[:4] == b"OggS":
            return "audio"
        # FLAC: starts with 'fLaC'
        if header[:4] == b"fLaC":
            return "audio"
        # WAV: starts with 'RIFF'
        if header[:4] == b"RIFF":
            return "audio"
        # WebM/Matroska: starts with 0x1A 0x45 0xDF 0xA3
        if header[:4] == b"\x1a\x45\xdf\xa3":
            return "video"
    except Exception:
        pass
    return _media_type_from_ext(file_path.suffix)


def _encode_media_url(dir_name: str, filename: str) -> str:
    """Encode media URL so browsers can fetch it correctly."""
    encoded_dir = quote(dir_name, safe="")
    encoded_file = quote(filename, safe="")
    return f"/api/media/{encoded_dir}/{encoded_file}"


async def scan_audiobooks() -> dict:
    """Scan audiobook_dir for new audiobook folders and import them.

    Supports two layouts:
    1. Each subfolder is one book: data/audiobooks/书名/001.mp3
    2. Root-level media files form one book: data/audiobooks/001.mp3
    """
    audiobook_dir = settings.audiobook_dir
    if not audiobook_dir.exists():
        audiobook_dir.mkdir(parents=True, exist_ok=True)
        return {"scanned": 0, "imported": 0, "skipped": 0}

    imported = 0
    skipped = 0

    db = await get_db()

    # Scan subfolders as individual books
    subfolders = [e for e in audiobook_dir.iterdir() if e.is_dir()]
    for entry in sorted(subfolders, key=lambda e: _natural_sort_key(e.name)):
        folder_name = entry.name
        cursor = await db.execute(
            "SELECT id FROM books WHERE media_root = ? AND source_url = ?",
            (folder_name, AUDIobook_SOURCE_URL),
        )
        if await cursor.fetchone():
            skipped += 1
            continue

        result = await import_audiobook_from_dir(folder_name)
        if result:
            imported += 1

    # Also check for root-level media files (treat as a single book)
    root_media = [
        f for f in audiobook_dir.iterdir()
        if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS
    ]
    if root_media:
        root_marker = "__root__"
        cursor = await db.execute(
            "SELECT id FROM books WHERE media_root = ? AND source_url = ?",
            (root_marker, AUDIobook_SOURCE_URL),
        )
        if not await cursor.fetchone():
            result = await _import_root_level_audiobook(root_media)
            if result:
                imported += 1
        else:
            skipped += 1

    return {"scanned": len(subfolders) + (1 if root_media else 0), "imported": imported, "skipped": skipped}


async def _import_root_level_audiobook(media_files: list[Path]) -> dict | None:
    """Import root-level media files as a single audiobook."""
    media_files.sort(key=lambda f: _natural_sort_key(f.name))

    book_url = f"{AUDIobook_SOURCE_URL}/__root__"
    source_url = AUDIobook_SOURCE_URL
    book_key = build_book_key(source_url, book_url)

    # Derive book name from parent directory
    book_name = settings.audiobook_dir.name

    db = await get_db()
    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url,
         category_name, total_chapters, media_root, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(book_key) DO UPDATE SET
            total_chapters = excluded.total_chapters,
            media_root = excluded.media_root,
            updated_at = excluded.updated_at""",
        (
            book_key,
            book_name,
            "",
            "",
            "",
            book_url,
            source_url,
            "有声书",
            len(media_files),
            "__root__",
        ),
    )

    book_id = await _get_book_id(db, book_url, source_url)

    await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM chapter_cache WHERE book_id = ?", (book_id,))

    for idx, media_file in enumerate(media_files):
        chapter_title = media_file.stem
        chapter_url = f"{book_url}#{idx}"
        media_type = _detect_media_type(media_file)

        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, chapter_title, chapter_url, idx),
        )

        manifest = json.dumps({
            "media_files": [{
                "filename": media_file.name,
                "url": _encode_media_url("__root__", media_file.name),
                "media_type": media_type,
            }]
        })
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'audiobook')""",
            (book_id, idx, chapter_title, chapter_url, manifest),
        )

    await db.commit()
    return {"book_id": book_id, "name": book_name, "chapters": len(media_files)}


async def import_audiobook_from_dir(dir_name: str) -> dict | None:
    """Import a single audiobook folder from audiobook_dir."""
    audiobook_dir = settings.audiobook_dir / dir_name
    if not audiobook_dir.exists() or not audiobook_dir.is_dir():
        return None

    media_files = [
        f for f in audiobook_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS
    ]
    if not media_files:
        return None

    media_files.sort(key=lambda f: _natural_sort_key(f.name))

    book_url = f"{AUDIobook_SOURCE_URL}/{dir_name}"
    source_url = AUDIobook_SOURCE_URL
    book_key = build_book_key(source_url, book_url)

    db = await get_db()
    await db.execute(
        """INSERT INTO books
        (book_key, name, author, cover_url, intro, book_url, source_url,
         category_name, total_chapters, media_root, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(book_key) DO UPDATE SET
            total_chapters = excluded.total_chapters,
            media_root = excluded.media_root,
            updated_at = excluded.updated_at""",
        (
            book_key,
            dir_name,
            "",
            "",
            "",
            book_url,
            source_url,
            "有声书",
            len(media_files),
            dir_name,
        ),
    )

    book_id = await _get_book_id(db, book_url, source_url)

    await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM chapter_cache WHERE book_id = ?", (book_id,))

    for idx, media_file in enumerate(media_files):
        # Compute relative path from audiobook folder for URL
        rel_path = media_file.relative_to(audiobook_dir)
        chapter_title = media_file.stem
        chapter_url = f"{book_url}#{idx}"
        media_type = _detect_media_type(media_file)

        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, chapter_title, chapter_url, idx),
        )

        manifest = json.dumps({
            "media_files": [{
                "filename": media_file.name,
                "url": _encode_media_url(dir_name, str(rel_path)),
                "media_type": media_type,
            }]
        })
        await db.execute(
            """INSERT INTO chapter_cache
            (book_id, chapter_idx, chapter_title, chapter_url, content, content_type)
            VALUES (?, ?, ?, ?, ?, 'audiobook')""",
            (book_id, idx, chapter_title, chapter_url, manifest),
        )

    await db.commit()
    return {"book_id": book_id, "name": dir_name, "chapters": len(media_files)}


async def import_audiobook_from_zip(file_name: str, raw_content: bytes) -> dict:
    """Import an audiobook from a ZIP file."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_content))
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")

    media_entries = [
        info for info in zf.infolist()
        if not info.is_dir() and Path(info.filename).suffix.lower() in MEDIA_EXTENSIONS
    ]
    if not media_entries:
        raise ValueError("ZIP contains no supported media files")

    media_entries.sort(key=lambda e: _natural_sort_key(Path(e.filename).name))

    digest = __import__('hashlib').sha1(raw_content).hexdigest()[:12]
    extract_dir = settings.audiobook_dir / digest
    extract_dir.mkdir(parents=True, exist_ok=True)

    for entry in media_entries:
        target = extract_dir / Path(entry.filename).name
        with zf.open(entry) as src, open(target, 'wb') as dst:
            shutil.copyfileobj(src, dst)

    result = await import_audiobook_from_dir(digest)
    if not result:
        raise RuntimeError("Failed to import audiobook from ZIP")
    return result


async def list_audiobooks() -> list[BookSchema]:
    """Get all audiobooks."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM books WHERE source_url = ? ORDER BY updated_at DESC""",
        (AUDIobook_SOURCE_URL,),
    )
    rows = await cursor.fetchall()
    return [
        BookSchema(
            id=row["id"],
            book_key=row["book_key"] or "",
            name=row["name"],
            author=row["author"] or "",
            cover_url=row["cover_url"] or "",
            intro=row["intro"] or "",
            book_url=row["book_url"],
            source_url=row["source_url"],
            category_name=row["category_name"] or "有声书",
            last_chapter=row["last_chapter"] or "",
            total_chapters=row["total_chapters"] or 0,
            media_root=row["media_root"] or "",
            added_at=row["added_at"] or "",
            updated_at=row["updated_at"] or "",
        )
        for row in rows
    ]


async def delete_audiobook(book_id: int) -> bool:
    """Delete an audiobook record. Does not delete disk files."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM books WHERE id = ? AND source_url = ?",
        (book_id, AUDIobook_SOURCE_URL),
    )
    await db.commit()
    return cursor.rowcount > 0


async def _get_book_id(db, book_url: str, source_url: str) -> int:
    cursor = await db.execute(
        "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
        (book_url, source_url),
    )
    row = await cursor.fetchone()
    return row["id"]
