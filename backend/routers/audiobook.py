"""Audiobook router — scan, import, list, and delete audiobooks."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.audiobook import (
    delete_audiobook,
    import_audiobook_from_zip,
    list_audiobooks,
    scan_audiobooks,
)
from backend.utils.upload_guard import validate_upload_size

router = APIRouter(prefix="/api/audiobook", tags=["audiobook"])


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


@router.delete("/{book_id}")
async def delete(book_id: int):
    deleted = await delete_audiobook(book_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return {"deleted": True}
