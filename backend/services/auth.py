import hashlib
import secrets
from datetime import datetime, timedelta

from backend.database import get_db


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash


def generate_token() -> str:
    return secrets.token_urlsafe(32)


async def create_token(device_name: str = "") -> str:
    from backend.config import settings

    db = await get_db()
    token = generate_token()
    expires_at = datetime.now() + timedelta(days=settings.token_expiry_days)

    await db.execute(
        "INSERT INTO auth_tokens (token, device_name, expires_at) VALUES (?, ?, ?)",
        (token, device_name, expires_at.isoformat()),
    )
    await db.commit()
    return token


async def verify_token(token: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT expires_at FROM auth_tokens WHERE token = ?",
        (token,),
    )
    row = await cursor.fetchone()

    if not row:
        return False

    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires_at:
        await db.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        await db.commit()
        return False

    await db.execute(
        "UPDATE auth_tokens SET last_used_at = datetime('now') WHERE token = ?",
        (token,),
    )
    await db.commit()
    return True
