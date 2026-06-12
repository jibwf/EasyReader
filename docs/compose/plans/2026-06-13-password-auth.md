# Password Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add password-based authentication with 90-day token expiry, supporting both PWA and e-ink clients.

**Architecture:** New auth API endpoints validate password and issue long-lived tokens. Tokens stored in SQLite with expiry. All API requests require valid token when READER_PASSWORD is configured.

**Tech Stack:** FastAPI, SHA256 hashing, aiosqlite, React (PWA), Kotlin (e-ink)

---

## Task 1: Database Schema - Auth Tokens Table

**Files:**
- Modify: `backend/database.py` - Add auth_tokens table to SCHEMA

- [ ] **Step 1: Add auth_tokens table**

```python
# backend/database.py - Add to SCHEMA string, after offline_catalog table

CREATE TABLE IF NOT EXISTS auth_tokens (
    token TEXT PRIMARY KEY,
    device_name TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_used_at TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Run tests to verify schema creation**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -c "from backend.database import get_db; import asyncio; asyncio.run(get_db()); print('Schema OK')"`
Expected: No errors, "Schema OK" printed

- [ ] **Step 3: Commit**

```bash
git add backend/database.py
git commit -m "feat: add auth_tokens table for password authentication"
```

---

## Task 2: Auth Configuration

**Files:**
- Modify: `backend/config.py` - Add password and token expiry settings

- [ ] **Step 1: Add auth settings**

```python
# backend/config.py - Add to Settings class

class Settings(BaseSettings):
    # ... existing fields ...
    password: str = ""  # Empty = auth disabled
    token_expiry_days: int = 90

    model_config = {"env_prefix": "READER_", "env_file": ".env"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.py
git commit -m "feat: add READER_PASSWORD and READER_TOKEN_EXPIRY_DAYS config"
```

---

## Task 3: Auth Service - Token Management

**Files:**
- Create: `backend/services/auth.py` - Token generation and verification
- Create: `tests/test_auth_service.py` - Tests for auth service

- [ ] **Step 1: Write auth service**

```python
# backend/services/auth.py
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
        (token, device_name, expires_at.isoformat())
    )
    await db.commit()
    return token


async def verify_token(token: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT expires_at FROM auth_tokens WHERE token = ?",
        (token,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return False
    
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires_at:
        # Token expired, delete it
        await db.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        await db.commit()
        return False
    
    # Update last_used_at
    await db.execute(
        "UPDATE auth_tokens SET last_used_at = datetime('now') WHERE token = ?",
        (token,)
    )
    await db.commit()
    return True
```

- [ ] **Step 2: Write tests**

```python
# tests/test_auth_service.py
import pytest
from backend.services.auth import hash_password, verify_password, generate_token
from backend.config import Settings


def test_hash_password():
    h = hash_password("test123")
    assert len(h) == 64  # SHA256 hex length
    assert h == hash_password("test123")  # Deterministic


def test_verify_password():
    h = hash_password("secret")
    assert verify_password("secret", h) is True
    assert verify_password("wrong", h) is False


def test_generate_token():
    t1 = generate_token()
    t2 = generate_token()
    assert len(t1) > 20
    assert t1 != t2  # Unique
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_auth_service.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/services/auth.py tests/test_auth_service.py
git commit -m "feat: add auth service for token management"
```

---

## Task 4: Auth API Endpoints

**Files:**
- Create: `backend/routers/auth.py` - Login and verify endpoints
- Modify: `backend/main.py` - Include auth router

- [ ] **Step 1: Create auth router**

```python
# backend/routers/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.services.auth import hash_password, verify_password, create_token, verify_token

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
    if not settings.password:
        raise HTTPException(status_code=400, detail="Authentication not configured")
    
    if not verify_password(req.password, hash_password(settings.password)):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    token = await create_token(req.device_name)
    return LoginResponse(token=token, expires_in_days=settings.token_expiry_days)


@router.get("/verify", response_model=VerifyResponse)
async def verify(token: str):
    valid = await verify_token(token)
    return VerifyResponse(valid=valid)
```

- [ ] **Step 2: Add router to main.py**

```python
# backend/main.py - Add import and include_router

from backend.routers import auth

app.include_router(auth.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/routers/auth.py backend/main.py
git commit -m "feat: add /api/auth/login and /api/auth/verify endpoints"
```

---

## Task 5: Auth Middleware - Protect API Routes

**Files:**
- Modify: `backend/main.py` - Update enforce_api_auth middleware

- [ ] **Step 1: Update middleware to check tokens**

```python
# backend/main.py - Replace enforce_api_auth middleware

@app.middleware("http")
async def enforce_api_auth(request: Request, call_next):
    # Skip auth for non-API routes and specific endpoints
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    
    # Public endpoints that don't require auth
    public_paths = ["/api/version", "/api/auth/login", "/api/auth/verify"]
    if request.url.path in public_paths:
        return await call_next(request)
    
    # If no password configured, skip auth
    if not settings.api_key and not settings.password:
        return await call_next(request)
    
    # Check API key first (existing mechanism)
    if settings.api_key:
        provided_key = request.headers.get("x-api-key", "")
        if provided_key == settings.api_key:
            return await call_next(request)
    
    # Check token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        from backend.services.auth import verify_token
        if await verify_token(token):
            return await call_next(request)
    
    return JSONResponse(status_code=401, content={"detail": "Invalid or missing authentication"})
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: protect API routes with token authentication"
```

---

## Task 6: PWA Frontend - Login UI

**Files:**
- Create: `frontend/src/components/LoginDialog.tsx` - Password input dialog
- Modify: `frontend/src/api/client.ts` - Add auth token handling
- Modify: `frontend/src/App.tsx` - Add login flow

- [ ] **Step 1: Create LoginDialog component**

```tsx
// frontend/src/components/LoginDialog.tsx
import { useState } from "react";

interface LoginDialogProps {
  onLogin: (token: string) => void;
}

export function LoginDialog({ onLogin }: LoginDialogProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password, device_name: navigator.userAgent }),
      });

      if (!res.ok) {
        setError("密码错误");
        return;
      }

      const data = await res.json();
      localStorage.setItem("reader-auth-token", data.token);
      localStorage.setItem("reader-auth-expires", String(Date.now() + data.expires_in_days * 86400000));
      onLogin(data.token);
    } catch {
      setError("连接失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-80 shadow-xl">
        <h2 className="text-lg font-semibold mb-4">输入密码访问</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="请输入密码"
            className="w-full px-3 py-2 border rounded-lg mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          {error && <p className="text-red-500 text-sm mb-3">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-500 text-white py-2 rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? "验证中..." : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update API client to send token**

```typescript
// frontend/src/api/client.ts - Update getClientRequestHeaders

export function getClientRequestHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init ?? {});
  headers.set("X-Client-Type", CLIENT_TYPE);
  headers.set("X-Client-Version", CLIENT_VERSION);
  headers.set("X-API-Contract-Version", API_CONTRACT_VERSION);
  
  // Send auth token if available
  const token = localStorage.getItem("reader-auth-token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  
  // Send API key if available (legacy)
  const apiKey = localStorage.getItem("reader-api-key") || "";
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }
  
  return headers;
}
```

- [ ] **Step 3: Update App.tsx to check auth**

```tsx
// frontend/src/App.tsx - Add auth check at top

import { useState, useEffect } from "react";
import { LoginDialog } from "./components/LoginDialog";

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("reader-auth-token");
    const expires = localStorage.getItem("reader-auth-expires");
    
    if (!token || !expires || Date.now() > Number(expires)) {
      setChecking(false);
      return;
    }
    
    // Verify token with server
    fetch(`/api/auth/verify?token=${token}`)
      .then(res => res.json())
      .then(data => {
        setAuthenticated(data.valid);
        setChecking(false);
      })
      .catch(() => setChecking(false));
  }, []);

  if (checking) {
    return <div className="flex items-center justify-center h-screen">加载中...</div>;
  }

  if (!authenticated) {
    return <LoginDialog onLogin={() => setAuthenticated(true)} />;
  }

  // ... rest of existing App component
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/LoginDialog.tsx frontend/src/api/client.ts frontend/src/App.tsx
git commit -m "feat: add login dialog and token-based auth for PWA"
```

---

## Task 7: Tests - Auth API Integration

**Files:**
- Create: `tests/test_auth_api.py` - Integration tests for auth endpoints

- [ ] **Step 1: Write auth API tests**

```python
# tests/test_auth_api.py
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_login_with_correct_password(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"password": "test123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["expires_in_days"] == 90


@pytest.mark.asyncio
async def test_login_with_wrong_password(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_valid_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        login_resp = await client.post("/api/auth/login", json={"password": "test123"})
        token = login_resp.json()["token"]
        
        # Verify token
        resp = await client.get(f"/api/auth/verify?token={token}")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(monkeypatch):
    monkeypatch.setattr("backend.config.settings", Settings(password="test123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        login_resp = await client.post("/api/auth/login", json={"password": "test123"})
        token = login_resp.json()["token"]
        
        # Access protected endpoint
        resp = await client.get("/api/books", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_auth_api.py -v`
Expected: 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth_api.py
git commit -m "test: add integration tests for auth API"
```

---

## Task 8: Final Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all new auth tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_auth.py tests/test_auth_service.py tests/test_auth_api.py -v`
Expected: All PASS

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_api_contract.py tests/test_database.py -v`
Expected: All PASS

- [ ] **Step 3: Update documentation**

Add to README.md:
```markdown
## 认证配置

设置密码保护系统访问：

```bash
# 设置密码（环境变量）
READER_PASSWORD=your-secret-password

# 可选：设置 Token 有效期（默认 90 天）
READER_TOKEN_EXPIRY_DAYS=90
```

首次访问时需要输入密码，验证通过后 Token 保存在浏览器/客户端本地，90 天内无需重新输入。
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add authentication configuration guide"
```
