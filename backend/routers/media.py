"""Media router — serve audiobook media files with Range request support."""

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


@router.get("/{folder_name}/{filename:path}")
async def serve_media(folder_name: str, filename: str):
    if ".." in folder_name or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    file_path = settings.audiobook_dir / folder_name / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content_type = AUDIO_VIDEO_TYPES.get(file_path.suffix.lower(), 'application/octet-stream')
    return FileResponse(path=str(file_path), media_type=content_type)
