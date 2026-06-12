from fastapi import HTTPException, UploadFile


def _get_settings():
    from backend.config import settings
    return settings


async def validate_upload_size(file: UploadFile, max_bytes: int | None = None):
    """Read file and enforce size limit. Raises 413 if too large."""
    settings = _get_settings()
    limit = max_bytes or settings.max_upload_size_bytes
    content = await file.read()
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
        )
    return content


def validate_list_length(items: list, max_items: int = 3000):
    """Validate list length to prevent memory exhaustion."""
    if len(items) > max_items:
        raise HTTPException(
            status_code=413,
            detail=f"List too large. Maximum {max_items} items allowed",
        )
