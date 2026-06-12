from fastapi import Header, HTTPException

from backend.config import settings


async def verify_api_key(x_api_key: str = Header(default="")):
    """Verify API key if one is configured. Empty configured key = auth disabled."""
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
