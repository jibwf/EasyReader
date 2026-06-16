"""Media router — serve audiobook media files with Range request support."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config import settings

router = APIRouter(prefix="/api/media", tags=["media"])

AUDIO_VIDEO_TYPES = {
    '.mp3': 'audio/mpeg',
    '.m4a': 'audio/mp4',
    '.wav': 'audio/wav',
    '.ogg': 'audio/ogg',
    '.flac': 'audio/flac',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mkv': 'video/x-matroska',
}

IMAGE_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
}


def _is_safe_path(file_path: Path, base_dir: Path) -> bool:
    """Check if resolved path is within base directory to prevent path traversal."""
    try:
        resolved = file_path.resolve()
        return resolved.is_relative_to(base_dir.resolve())
    except (ValueError, OSError):
        return False


@router.get("/covers/{filename:path}")
async def serve_cover(filename: str):
    """Serve audiobook cover images."""
    file_path = settings.audiobook_cover_dir / filename
    
    if not _is_safe_path(file_path, settings.audiobook_cover_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Cover not found")

    content_type = IMAGE_TYPES.get(file_path.suffix.lower(), 'application/octet-stream')
    return FileResponse(path=str(file_path), media_type=content_type)


@router.get("/{folder_name}/{filename:path}")
async def serve_media(folder_name: str, filename: str):
    file_path = settings.audiobook_dir / folder_name / filename
    
    if not _is_safe_path(file_path, settings.audiobook_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content_type = AUDIO_VIDEO_TYPES.get(file_path.suffix.lower(), 'application/octet-stream')
    return FileResponse(path=str(file_path), media_type=content_type)
