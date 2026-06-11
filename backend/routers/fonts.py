from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.models.font import ServerFontItem
from backend.services.font_library import (
    get_font_media_type,
    get_server_font_file,
    list_server_fonts,
)

router = APIRouter(prefix="/api/fonts", tags=["fonts"])


@router.get("", response_model=list[ServerFontItem])
async def get_fonts():
    return [ServerFontItem(**item) for item in list_server_fonts()]


@router.get("/{font_file_name:path}/download")
async def download_font(font_file_name: str):
    try:
        font_path = get_server_font_file(font_file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Font not found") from exc

    return FileResponse(
        path=font_path,
        filename=font_path.name,
        media_type=get_font_media_type(font_path),
    )
