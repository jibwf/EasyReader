# EasyReader Security Fixes Implementation Plan

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/security-fixes.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 critical/high-severity security issues identified in the audit: API key authentication, file size limits, CORS restriction, and _SOURCE_HEALTH memory leak.

**Architecture:** Add API key authentication via FastAPI dependency injection, enforce file size limits using FastAPI's built-in body size constraints, restrict CORS to configurable origins, and cap _SOURCE_HEALTH with an LRU eviction strategy.

**Tech Stack:** FastAPI, Pydantic Settings, Python standard library (collections.OrderedDict for LRU)

---

## Task 1: API Key Authentication

**Covers:** Audit §1.1 "无认证/授权系统"

**Files:**
- Modify: `backend/config.py` — add `api_key` setting
- Create: `backend/auth.py` — API key verification dependency
- Modify: `backend/main.py` — apply auth dependency to API routes
- Create: `tests/test_auth.py` — tests for auth behavior
- Modify: `frontend/src/api/client.ts` — send API key header

- [ ] **Step 1: Add api_key setting to config**

```python
# backend/config.py — add to Settings class
class Settings(BaseSettings):
    # ... existing fields ...
    api_key: str = ""  # Empty = auth disabled (backward compatible)

    model_config = {"env_prefix": "READER_", "env_file": ".env"}
```

- [ ] **Step 2: Create auth dependency**

```python
# backend/auth.py
from fastapi import Header, HTTPException, Depends

from backend.config import settings


async def verify_api_key(x_api_key: str = Header(default="")):
    """Verify API key if one is configured. Empty configured key = auth disabled."""
    if not settings.api_key:
        return  # No key configured, auth disabled
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

- [ ] **Step 3: Apply auth to all API routes**

In `backend/main.py`, apply the dependency to the app's dependencies list so it covers all `/api/*` routes:

```python
# backend/main.py — add import and apply to app
from backend.auth import verify_api_key

app = FastAPI(title="EasyReader", version="0.1.0", lifespan=lifespan)
app.dependency_overrides = {}  # No overrides needed

# Add global dependency for /api/* routes
@app.middleware("http")
async def enforce_api_auth(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/version":
        if settings.api_key:
            provided_key = request.headers.get("x-api-key", "")
            if provided_key != settings.api_key:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)
```

- [ ] **Step 4: Write auth tests**

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_no_api_key_configured_allows_all(monkeypatch):
    """When READER_API_KEY is empty, all requests pass without auth."""
    monkeypatch.setattr("backend.config.settings", Settings(api_key=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_key_required_rejects_missing(monkeypatch):
    """When READER_API_KEY is set, requests without key get 401."""
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books")
        assert resp.status_code == 401
        assert "Invalid or missing API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_required_rejects_wrong_key(monkeypatch):
    """When READER_API_KEY is set, wrong key gets 401."""
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books", headers={"x-api-key": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_required_accepts_correct_key(monkeypatch):
    """When READER_API_KEY is set, correct key passes."""
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/books", headers={"x-api-key": "secret123"})
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_version_endpoint_always_accessible(monkeypatch):
    """/api/version is always accessible regardless of auth."""
    monkeypatch.setattr("backend.config.settings", Settings(api_key="secret123"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/version")
        assert resp.status_code == 200
```

- [ ] **Step 5: Run auth tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 5 tests PASS

- [ ] **Step 6: Update frontend to send API key**

```typescript
// frontend/src/api/client.ts — add to buildHeaders or request function
const apiKey = localStorage.getItem("reader-api-key") || "";
if (apiKey) {
    headers["X-API-Key"] = apiKey;
}
```

- [ ] **Step 7: Commit**

```bash
git add backend/config.py backend/auth.py backend/main.py tests/test_auth.py frontend/src/api/client.ts
git commit -m "feat: add optional API key authentication to all API endpoints

When READER_API_KEY env var is set, all /api/* endpoints (except /api/version)
require X-API-Key header. Empty key disables auth for backward compatibility."
```

---

## Task 2: File Upload Size Limits

**Covers:** Audit §1.1 "无文件大小限制"

**Files:**
- Modify: `backend/config.py` — add `max_upload_size_mb` setting
- Modify: `backend/main.py` — add request body size middleware
- Modify: `backend/routers/books.py` — validate upload size
- Modify: `backend/routers/backup.py` — validate upload size
- Modify: `backend/routers/sources.py` — validate list length
- Create: `tests/test_upload_limits.py` — tests for size enforcement

- [ ] **Step 1: Add upload size config**

```python
# backend/config.py — add to Settings class
class Settings(BaseSettings):
    # ... existing fields ...
    max_upload_size_mb: int = 50  # Max file upload size in MB

    model_config = {"env_prefix": "READER_", "env_file": ".env"}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024
```

- [ ] **Step 2: Add upload size validation helper**

```python
# backend/utils/upload_guard.py
from fastapi import HTTPException, UploadFile

from backend.config import settings


async def validate_upload_size(file: UploadFile, max_bytes: int | None = None):
    """Read file and enforce size limit. Raises 413 if too large."""
    limit = max_bytes or settings.max_upload_size_bytes
    content = await file.read()
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
        )
    return content


def validate_list_length(items: list, max_items: int = 1000):
    """Validate list length to prevent memory exhaustion."""
    if len(items) > max_items:
        raise HTTPException(
            status_code=413,
            detail=f"List too large. Maximum {max_items} items allowed",
        )
```

- [ ] **Step 3: Apply to books import endpoint**

```python
# backend/routers/books.py — modify import_books
@router.post("/import")
async def import_books(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    raw = await validate_upload_size(file)
    # ... rest of existing logic unchanged ...
```

- [ ] **Step 4: Apply to backup restore endpoint**

```python
# backend/routers/backup.py — modify restore_backup
@router.post("/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    file: UploadFile = File(...),
    mode: BackupRestoreMode = Query(default="incremental"),
    conflict_policy: BackupConflictPolicy = Query(default="backup_wins"),
):
    raw_archive = await validate_upload_size(file)
    # ... rest of existing logic unchanged ...
```

- [ ] **Step 5: Apply to sources import endpoint**

```python
# backend/routers/sources.py — add list length validation
@router.post("/import", response_model=ImportResponse)
async def import_sources(sources: list[dict]):
    validate_list_length(sources)
    count = await source_manager.import_sources(sources)
    return ImportResponse(count=count)
```

- [ ] **Step 6: Write upload limit tests**

```python
# tests/test_upload_limits.py
import io
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_books_import_rejects_oversized_file(monkeypatch):
    """File exceeding max_upload_size_mb returns 413."""
    monkeypatch.setattr("backend.config.settings", Settings(max_upload_size_mb=1))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a file > 1MB
        large_content = b"x" * (2 * 1024 * 1024)
        resp = await client.post(
            "/api/books/import",
            files={"file": ("test.txt", io.BytesIO(large_content), "text/plain")},
        )
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sources_import_rejects_long_list():
    """Source list exceeding 1000 items returns 413."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sources = [{"book_source_url": f"http://example.com/{i}"} for i in range(1001)]
        resp = await client.post("/api/sources/import", json=sources)
        assert resp.status_code == 413
        assert "List too large" in resp.json()["detail"]
```

- [ ] **Step 7: Run upload limit tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_upload_limits.py -v`
Expected: 2 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/config.py backend/utils/upload_guard.py backend/routers/books.py backend/routers/backup.py backend/routers/sources.py tests/test_upload_limits.py
git commit -m "feat: enforce file upload size limits and list length caps

- Default 50MB upload limit (configurable via READER_MAX_UPLOAD_SIZE_MB)
- 1000 item limit on source import lists
- Returns 413 with clear error message when exceeded"
```

---

## Task 3: CORS Restriction

**Covers:** Audit §1.2 "CORS 完全开放"

**Files:**
- Modify: `backend/config.py` — add `cors_origins` setting
- Modify: `backend/main.py` — use configurable CORS origins
- Create: `tests/test_cors.py` — tests for CORS behavior

- [ ] **Step 1: Add CORS origins config**

```python
# backend/config.py — add to Settings class
class Settings(BaseSettings):
    # ... existing fields ...
    cors_origins: str = "*"  # Comma-separated origins, or "*" for all

    model_config = {"env_prefix": "READER_", "env_file": ".env"}

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

- [ ] **Step 2: Update CORS middleware in main.py**

```python
# backend/main.py — replace CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 3: Write CORS tests**

```python
# tests/test_cors.py
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import Settings


@pytest.mark.asyncio
async def test_cors_wildcard_allows_all_origins(monkeypatch):
    """Default config with * allows any origin."""
    monkeypatch.setattr("backend.config.settings", Settings(cors_origins="*"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/api/books",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_specific_origins(monkeypatch):
    """Configured origins restrict which origins are allowed."""
    monkeypatch.setattr("backend.config.settings", Settings(cors_origins="http://localhost:5173,https://example.com"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Allowed origin
        resp = await client.options(
            "/api/books",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

        # Disallowed origin
        resp = await client.options(
            "/api/books",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in resp.headers
```

- [ ] **Step 4: Run CORS tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_cors.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/main.py tests/test_cors.py
git commit -m "feat: make CORS origins configurable via READER_CORS_ORIGINS

Default remains * for backward compatibility. Set READER_CORS_ORIGINS
to comma-separated list of allowed origins for production deployments."
```

---

## Task 4: Fix _SOURCE_HEALTH Memory Leak

**Covers:** Audit §2.1 "内存泄漏 - _SOURCE_HEALTH"

**Files:**
- Modify: `backend/services/search.py` — cap _SOURCE_HEALTH with LRU eviction
- Create: `tests/test_search_health_leak.py` — tests for eviction behavior

- [ ] **Step 1: Add LRU cap to _SOURCE_HEALTH**

```python
# backend/services/search.py — replace _SOURCE_HEALTH definition
from collections import OrderedDict

MAX_SOURCE_HEALTH_ENTRIES = 500

_SOURCE_HEALTH: OrderedDict[str, SourceHealthState] = OrderedDict()
```

- [ ] **Step 2: Add eviction helper**

```python
# backend/services/search.py — add after _SOURCE_HEALTH definition
def _evict_source_health():
    """Remove oldest entries when exceeding cap."""
    while len(_SOURCE_HEALTH) > MAX_SOURCE_HEALTH_ENTRIES:
        _SOURCE_HEALTH.popitem(last=False)  # Remove oldest (FIFO)
```

- [ ] **Step 3: Update _record_source_success and _record_source_failure**

```python
# backend/services/search.py — modify _record_source_success
def _record_source_success(source_url: str, latency_ms: float):
    state = _SOURCE_HEALTH.setdefault(source_url, SourceHealthState())
    _SOURCE_HEALTH.move_to_end(source_url)  # Mark as recently used
    state.success_count += 1
    if state.avg_latency_ms <= 0:
        state.avg_latency_ms = latency_ms
    else:
        state.avg_latency_ms = state.avg_latency_ms * 0.7 + latency_ms * 0.3
    state.last_error = ""
    state.last_success_at = time()
    state.updated_at = time()
    _evict_source_health()


# backend/services/search.py — modify _record_source_failure
def _record_source_failure(source_url: str, latency_ms: float, error: str, timed_out: bool):
    state = _SOURCE_HEALTH.setdefault(source_url, SourceHealthState())
    _SOURCE_HEALTH.move_to_end(source_url)  # Mark as recently used
    state.failure_count += 1
    if timed_out:
        state.timeout_count += 1
    if state.avg_latency_ms <= 0:
        state.avg_latency_ms = latency_ms
    else:
        state.avg_latency_ms = state.avg_latency_ms * 0.75 + latency_ms * 0.25
    state.last_error = (error or "search-failed")[:200]
    state.updated_at = time()
    _evict_source_health()
```

- [ ] **Step 4: Write memory leak tests**

```python
# tests/test_search_health_leak.py
import pytest
from backend.services.search import (
    _SOURCE_HEALTH,
    _record_source_success,
    _record_source_failure,
    MAX_SOURCE_HEALTH_ENTRIES,
    SourceHealthState,
)


@pytest.fixture(autouse=True)
def clean_health():
    """Reset _SOURCE_HEALTH between tests."""
    _SOURCE_HEALTH.clear()
    yield
    _SOURCE_HEALTH.clear()


def test_source_health_does_not_exceed_cap():
    """_SOURCE_HEALTH should never exceed MAX_SOURCE_HEALTH_ENTRIES."""
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 100):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES


def test_eviction_removes_oldest():
    """Oldest entries should be evicted first."""
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 10):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    # First 10 entries should have been evicted
    assert "http://source-0.com" not in _SOURCE_HEALTH
    assert "http://source-9.com" not in _SOURCE_HEALTH
    # Later entries should still exist
    assert f"http://source-{MAX_SOURCE_HEALTH_ENTRIES + 9}.com" in _SOURCE_HEALTH


def test_recently_accessed_entry_not_evicted():
    """Recently accessed entries should not be evicted."""
    # Fill to capacity
    for i in range(MAX_SOURCE_HEALTH_ENTRIES):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    # Access first entry to move it to end
    _record_source_success("http://source-0.com", latency_ms=100.0)
    # Add one more to trigger eviction
    _record_source_success("http://source-new.com", latency_ms=100.0)
    # source-0 should survive because it was recently accessed
    assert "http://source-0.com" in _SOURCE_HEALTH
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES


def test_failure_records_also_trigger_eviction():
    """Failures should also be subject to eviction."""
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 5):
        _record_source_failure(f"http://source-{i}.com", latency_ms=500.0, error="timeout", timed_out=True)
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES
```

- [ ] **Step 5: Run memory leak tests**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_search_health_leak.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest -v`
Expected: All existing + new tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/search.py tests/test_search_health_leak.py
git commit -m "fix: cap _SOURCE_HEALTH dict at 500 entries with LRU eviction

Prevents unbounded memory growth from accumulating source health states.
Least recently accessed entries are evicted when the cap is exceeded."
```

---

## Task 5: Final Verification

**Covers:** All tasks above

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest -v`
Expected: All tests PASS (existing 85 + new ~11)

- [ ] **Step 2: Verify no regressions in existing API**

Run: `cd /Users/bowji/Downloads/EasyReader && .venv/bin/python -m pytest tests/test_api_contract.py tests/test_books_api.py -v`
Expected: All PASS

- [ ] **Step 3: Final commit summary**

```bash
git log --oneline -5
```

Expected: 4 new commits for auth, upload limits, CORS, and memory leak fix
