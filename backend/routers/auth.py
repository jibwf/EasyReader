from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


def _get_settings():
    from backend.config import settings
    return settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str
    device_name: str = ""


class LoginResponse(BaseModel):
    token: str
    expires_in_days: int


class VerifyResponse(BaseModel):
    valid: bool


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    settings = _get_settings()
    if not settings.password:
        raise HTTPException(status_code=400, detail="Authentication not configured")

    from backend.services.auth import hash_password, verify_password, create_token
    if not verify_password(req.password, hash_password(settings.password)):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = await create_token(req.device_name)
    return LoginResponse(token=token, expires_in_days=settings.token_expiry_days)


@router.get("/verify", response_model=VerifyResponse)
async def verify(token: str):
    from backend.services.auth import verify_token
    valid = await verify_token(token)
    return VerifyResponse(valid=valid)
