"""Audiobook router — scan, import, list, and delete audiobooks."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.database import get_db
from backend.services.audiobook import (
    delete_audiobook,
    import_audiobook_from_zip,
    list_audiobooks,
    scan_audiobooks,
)
from backend.services.douban_cover import fetch_cover_from_douban_url
from backend.utils.upload_guard import validate_upload_size

router = APIRouter(prefix="/api/audiobook", tags=["audiobook"])


class SetCoverRequest(BaseModel):
    book_id: int
    douban_url: str


@router.post("/scan")
async def scan():
    result = await scan_audiobooks()
    return result


@router.post("/import-zip")
async def import_zip(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    raw = await validate_upload_size(file)
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        result = await import_audiobook_from_zip(file.filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"message": "imported", **result}


@router.get("/list")
async def list_all():
    books = await list_audiobooks()
    return books


class DeleteAudiobookRequest(BaseModel):
    delete_files: bool = False


@router.delete("/{book_id}")
async def delete(book_id: int, delete_files: bool = False):
    result = await delete_audiobook(book_id, delete_files)
    if not result["deleted"]:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return result


@router.post("/set-cover")
async def set_cover(request: SetCoverRequest):
    """Set audiobook cover from Douban URL."""
    db = await get_db()
    cursor = await db.execute("SELECT id, name FROM books WHERE id = ?", (request.book_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    
    cover_path = await fetch_cover_from_douban_url(request.douban_url, row["name"])
    if not cover_path:
        raise HTTPException(status_code=400, detail="Failed to fetch cover from Douban")
    
    await db.execute("UPDATE books SET cover_url = ? WHERE id = ?", (cover_path, request.book_id))
    await db.commit()
    
    return {"cover_url": cover_path}
