"""Audiobook service — scan, import, and manage audiobooks."""

import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import quote

from backend.services.douban_cover import search_douban_cover, download_cover, get_cover_extension

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.database import get_db
from backend.models.book import BookSchema
from backend.utils.book_key import build_book_key

AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.ogg', '.flac'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv'}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

AUDIobook_SOURCE_URL = "local://audiobook"

# Browser-compatible audio codecs in MP4 container
_BROWSER_COMPATIBLE_AUDIO = {"aac", "opus"}


def _natural_sort_key(s: str):
    """Sort strings with embedded numbers naturally."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def _encode_media_url(dir_name: str, filename: str) -> str:
    """Encode media URL path segments for browser compatibility."""
    encoded_dir = quote(dir_name, safe="")
    encoded_file = quote(filename, safe="")
    return f"/api/media/{encoded_dir}/{encoded_file}"


def _detect_media_type_from_header(file_path: Path) -> str:
    """Detect media type from file header: ftyp = video, else = audio."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        if len(header) >= 8 and header[4:8] == b"ftyp":
            return "video"
    except Exception:
        pass
    return "audio"


def _probe_codecs(file_path: Path) -> tuple[str, str]:
    """Use ffprobe to detect video and audio codecs. Returns (video_codec, audio_codec)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return ("", "")
        probe = json.loads(result.stdout)
        video_codec = ""
        audio_codec = ""
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video" and not video_codec:
                video_codec = stream.get("codec_name", "")
            elif stream.get("codec_type") == "audio" and not audio_codec:
                audio_codec = stream.get("codec_name", "")
        return (video_codec, audio_codec)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return ("", "")


def _needs_transcode(file_path: Path) -> bool:
    """Check if a file needs transcoding for browser compatibility.
    
    Transcode if:
    1. MP4 container with incompatible audio codec (e.g. H264+MP3)
    2. Non-MP4 container (MPEG-TS, etc.) — convert to MP4 for browser playback
    """
    video_codec, audio_codec = _probe_codecs(file_path)
    
    if not audio_codec:
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
            if len(header) >= 8 and header[4:8] == b"ftyp":
                return False
            return True
        except Exception:
            return False
    
    if audio_codec.lower() not in _BROWSER_COMPATIBLE_AUDIO:
        return True
    
    return False


def _transcode_to_compatible(file_path: Path) -> Path | None:
    """Transcode a file to browser-compatible MP4 (H264+AAC). Returns the new path or None."""
    output_path = file_path.with_suffix(".compatible.mp4")
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", str(file_path),
             "-c:v", "copy",
             "-c:a", "aac", "-b:a", "128k",
             "-y", str(output_path)],
            capture_output=True, timeout=600,
        )
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            file_path.unlink()
            output_path.rename(file_path)
            return file_path
        else:
            if output_path.exists():
                output_path.unlink()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("ffmpeg transcoding failed for %s: %s", file_path, e)
        if output_path.exists():
            output_path.unlink()
    return None


def _process_media_file(media_file: Path, dir_name: str, audiobook_dir: Path) -> dict:
    """Process a single media file: transcode if needed, generate manifest entry."""
    if _needs_transcode(media_file):
        transcoded = _transcode_to_compatible(media_file)
        if transcoded:
            media_file = transcoded

    rel_path = media_file.relative_to(audiobook_dir)
    media_type = _detect_media_type_from_header(media_file)

    return {
        "filename": media_file.name,
        "url": _encode_media_url(dir_name, str(rel_path)),
        "media_type": media_type,
    }


async def scan_audiobooks() -> dict:
    """Scan audiobook_dir for new audiobook folders and import them.

    Supports two layouts:
    1. Each subfolder is one book: data/audiobooks/书名/001.mp3
    2. Root-level media files form one book: data/audiobooks/001.mp3
    
    Also checks existing audiobooks for missing covers and fetches from Douban.
    Detects orphaned records (files deleted but DB entry remains).
    """
    audiobook_dir = settings.audiobook_dir
    if not audiobook_dir.exists():
        audiobook_dir.mkdir(parents=True, exist_ok=True)
        return {"scanned": 0, "imported": 0, "skipped": 0, "covers_fetched": 0, "logs": ["创建 audiobook 目录"], "orphaned": []}

    imported = 0
    skipped = 0
    covers_fetched = 0
    logs: list[str] = []
    orphaned: list[dict] = []  # Books in DB but files missing

    db = await get_db()

    # Get all existing audiobook folder names on disk
    subfolders = [e for e in audiobook_dir.iterdir() if e.is_dir()]
    folder_names = {e.name for e in subfolders}
    logs.append(f"扫描到 {len(subfolders)} 个文件夹")

    # Scan subfolders as individual books
    for entry in sorted(subfolders, key=lambda e: _natural_sort_key(e.name)):
        folder_name = entry.name
        cursor = await db.execute(
            "SELECT id, name, cover_url FROM books WHERE media_root = ? AND source_url = ?",
            (folder_name, AUDIobook_SOURCE_URL),
        )
        row = await cursor.fetchone()
        if row:
            logs.append(f"《{folder_name}》已存在")
            # Check if cover is missing
            if not row["cover_url"]:
                logs.append(f"《{folder_name}》缺少封面，搜索豆瓣...")
                cover_url = await _fetch_cover_for_audiobook(folder_name)
                if cover_url:
                    await db.execute(
                        "UPDATE books SET cover_url = ? WHERE id = ?",
                        (cover_url, row["id"]),
                    )
                    covers_fetched += 1
                    logs.append(f"《{folder_name}》封面已保存")
                else:
                    logs.append(f"《{folder_name}》未找到封面")
            else:
                logs.append(f"《{folder_name}》封面已存在")
            skipped += 1
            continue

        logs.append(f"导入《{folder_name}》...")
        result = await import_audiobook_from_dir(folder_name)
        if result:
            imported += 1
            logs.append(f"《{folder_name}》导入成功（{result.get('chapters', 0)} 章）")
        else:
            logs.append(f"《{folder_name}》导入失败：未找到媒体文件")

    # Check for root-level media files
    root_media = [
        f for f in audiobook_dir.iterdir()
        if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS
    ]
    if root_media:
        logs.append(f"发现 {len(root_media)} 个根目录媒体文件")
        root_marker = "__root__"
        cursor = await db.execute(
            "SELECT id, name, cover_url FROM books WHERE media_root = ? AND source_url = ?",
            (root_marker, AUDIobook_SOURCE_URL),
        )
        row = await cursor.fetchone()
        if row:
            logs.append("根目录有声书已存在")
            if not row["cover_url"]:
                book_name = audiobook_dir.name
                logs.append(f"搜索《{book_name}》封面...")
                cover_url = await _fetch_cover_for_audiobook(book_name)
                if cover_url:
                    await db.execute(
                        "UPDATE books SET cover_url = ? WHERE id = ?",
                        (cover_url, row["id"]),
                    )
                    covers_fetched += 1
                    logs.append(f"《{book_name}》封面已保存")
                else:
                    logs.append(f"《{book_name}》未找到封面")
            skipped += 1
        else:
            logs.append("导入根目录有声书...")
            result = await _import_root_level_audiobook(root_media)
            if result:
                imported += 1
                logs.append("根目录有声书导入成功")
            else:
                logs.append("根目录有声书导入失败")

    # Find orphaned records: books in DB but folder/file no longer exists
    cursor = await db.execute(
        "SELECT id, name, media_root FROM books WHERE source_url = ?",
        (AUDIobook_SOURCE_URL,),
    )
    all_db_books = await cursor.fetchall()
    
    for book in all_db_books:
        media_root = book["media_root"]
        if media_root == "__root__":
            # Check if root-level files still exist
            if not root_media:
                orphaned.append({"id": book["id"], "name": book["name"], "media_root": media_root})
        else:
            # Check if folder still exists
            if media_root not in folder_names:
                orphaned.append({"id": book["id"], "name": book["name"], "media_root": media_root})

    if orphaned:
        logs.append(f"发现 {len(orphaned)} 个孤立记录（文件已删除）")

    await db.commit()
    return {
        "scanned": len(subfolders) + (1 if root_media else 0),
        "imported": imported,
        "skipped": skipped,
        "covers_fetched": covers_fetched,
        "logs": logs,
        "orphaned": orphaned,
    }


async def _fetch_cover_for_audiobook(book_name: str) -> str | None:
    """Fetch cover from Douban for an audiobook.
    
    Args:
        book_name: Name of the audiobook
        
    Returns:
        Cover URL or None if not found
    """
    try:
        cover_url = await search_douban_cover(book_name)
        if cover_url:
            logger.info("Fetched cover for '%s': %s", book_name, cover_url)
            return cover_url
    except Exception as e:
        logger.warning("Failed to fetch cover for '%s': %s", book_name, e)
    return None


async def _import_root_level_audiobook(media_files: list[Path]) -> dict | None:
    """Import root-level media files as a single audiobook."""
    media_files.sort(key=lambda f: _natural_sort_key(f.name))

    book_url = f"{AUDIobook_SOURCE_URL}/__root__"
    source_url = AUDIobook_SOURCE_URL
    book_key = build_book_key(source_url, book_url)

    # Derive book name from parent directory
    book_name = settings.audiobook_dir.name

    # Try to fetch cover from Douban
    cover_url = ""
    try:
        douban_cover = await search_douban_cover(book_name)
        if douban_cover:
            cover_url = douban_cover
            logger.info("Found Douban cover for '%s': %s", book_name, cover_url)
    except Exception as e:
        logger.warning("Failed to fetch Douban cover for '%s': %s", book_name, e)

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
            cover_url,
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
        manifest_entry = _process_media_file(media_file, "__root__", settings.audiobook_dir)
        chapter_title = media_file.stem
        chapter_url = f"{book_url}#{idx}"

        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, chapter_title, chapter_url, idx),
        )

        manifest = json.dumps({"media_files": [manifest_entry]})
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

    # Try to fetch cover from Douban
    cover_url = ""
    try:
        douban_cover = await search_douban_cover(dir_name)
        if douban_cover:
            cover_url = douban_cover
            logger.info("Found Douban cover for '%s': %s", dir_name, cover_url)
    except Exception as e:
        logger.warning("Failed to fetch Douban cover for '%s': %s", dir_name, e)

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
            cover_url,
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
        manifest_entry = _process_media_file(media_file, dir_name, audiobook_dir)
        chapter_title = media_file.stem
        chapter_url = f"{book_url}#{idx}"

        await db.execute(
            "INSERT INTO chapters (book_id, title, url, idx, cached) VALUES (?, ?, ?, ?, 1)",
            (book_id, chapter_title, chapter_url, idx),
        )

        manifest = json.dumps({"media_files": [manifest_entry]})
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

    digest = hashlib.sha1(raw_content).hexdigest()[:12]
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


async def delete_audiobook(book_id: int, delete_files: bool = False) -> dict:
    """Delete an audiobook record and optionally delete disk files.
    
    Args:
        book_id: Book ID to delete
        delete_files: If True, also delete the media folder from disk
        
    Returns:
        Dict with deletion result info
    """
    db = await get_db()
    
    # Get book info before deletion
    cursor = await db.execute(
        "SELECT id, name, media_root FROM books WHERE id = ? AND source_url = ?",
        (book_id, AUDIobook_SOURCE_URL),
    )
    row = await cursor.fetchone()
    if not row:
        return {"deleted": False}
    
    book_name = row["name"]
    media_root = row["media_root"]
    
    # Delete from database
    await db.execute(
        "DELETE FROM books WHERE id = ? AND source_url = ?",
        (book_id, AUDIobook_SOURCE_URL),
    )
    await db.commit()
    
    # Optionally delete files from disk
    files_deleted = False
    if delete_files and media_root:
        audiobook_dir = settings.audiobook_dir
        if media_root == "__root__":
            target_dir = audiobook_dir
        else:
            target_dir = audiobook_dir / media_root
        
        if target_dir.exists():
            import shutil
            try:
                if target_dir.is_dir():
                    shutil.rmtree(target_dir)
                else:
                    target_dir.unlink()
                files_deleted = True
            except Exception:
                pass
    
    return {"deleted": True, "name": book_name, "files_deleted": files_deleted}


async def _get_book_id(db, book_url: str, source_url: str) -> int:
    cursor = await db.execute(
        "SELECT id FROM books WHERE book_url = ? AND source_url = ?",
        (book_url, source_url),
    )
    row = await cursor.fetchone()
    return row["id"]
