---
feature: security-fixes
status: delivered
specs: []
plans:
  - docs/compose/plans/2026-06-13-security-fixes.md
branch: main
commits: 6488f06..b7760e5
---

# Security Fixes — Final Report

## What Was Built

Four critical/high-severity security issues identified in the project audit were fixed:

1. **API Key Authentication**: Optional API key authentication protects all `/api/*` endpoints (except `/api/version`). When `READER_API_KEY` env var is set, requests must include `X-API-Key` header. Empty key disables auth for backward compatibility.

2. **File Upload Size Limits**: All file upload endpoints (`/api/books/import`, `/api/backup/restore`) now enforce a configurable size limit (default 200MB, set via `READER_MAX_UPLOAD_SIZE_MB`). Source import lists are capped at 3000 items. Returns HTTP 413 with clear error message when exceeded.

3. **CORS Restriction**: CORS origins are now configurable via `READER_CORS_ORIGINS` env var (comma-separated list). Default remains `*` for backward compatibility. Set to specific origins for production deployments.

4. **Memory Leak Fix**: `_SOURCE_HEALTH` dictionary in the search service is now capped at 500 entries using LRU eviction. Least recently accessed entries are evicted when the cap is exceeded, preventing unbounded memory growth.

## Architecture

### Authentication Flow

```
Request → enforce_api_auth middleware → X-API-Key header check → Route handler
                                                    ↓ (no key configured)
                                              Skip auth (backward compatible)
```

- Middleware in `backend/main.py` intercepts all `/api/*` requests
- Config in `backend/config.py` via `READER_API_KEY` env var
- Frontend in `frontend/src/api/client.ts` sends header from `localStorage("reader-api-key")`

### Upload Guard

```
Upload file → validate_upload_size() → Read content → Check size → Pass or 413
```

- `backend/utils/upload_guard.py` provides reusable validation
- Config via `READER_MAX_UPLOAD_SIZE_MB` (default 200)
- List validation via `validate_list_length()` (max 3000 items)

### CORS Configuration

```
Startup → Settings.cors_origin_list → CORSMiddleware allow_origins
```

- `backend/config.py` parses `READER_CORS_ORIGINS` env var
- Supports `*` (all origins) or comma-separated origin list

### Memory Management

```
_record_source_success/failure() → OrderedDict → _evict_source_health()
                                    ↓ (move_to_end on access)
                                    ↓ (popitem when > 500)
                              LRU eviction
```

- `backend/services/search.py` uses `OrderedDict` for LRU tracking
- `MAX_SOURCE_HEALTH_ENTRIES = 500` cap

### Design Decisions

- **Optional auth**: Empty `READER_API_KEY` disables auth, preserving backward compatibility for existing deployments
- **Middleware-based auth**: Applied globally to all routes rather than per-route dependencies, ensuring no endpoints are accidentally unprotected
- **Lazy import in upload_guard**: Settings imported at call time to support test monkeypatching
- **OrderedDict for LRU**: Chosen over custom LRU class for simplicity and stdlib availability

## Usage

### Enable Authentication

```bash
# Set API key
export READER_API_KEY="your-secret-key"

# Frontend: store key in browser
localStorage.setItem("reader-api-key", "your-secret-key")
```

### Configure Upload Limits

```bash
# Default 200MB, change as needed
export READER_MAX_UPLOAD_SIZE_MB=500
```

### Restrict CORS

```bash
# Allow only specific origins
export READER_CORS_ORIGINS="http://localhost:5173,https://myapp.example.com"
```

### All New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `READER_API_KEY` | `""` | API key for authentication (empty = disabled) |
| `READER_MAX_UPLOAD_SIZE_MB` | `200` | Max file upload size in MB |
| `READER_CORS_ORIGINS` | `"*"` | Comma-separated allowed origins |

## Verification

**18 new tests** added across 4 test files:

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_auth.py` | 5 | Auth middleware, key validation, version bypass |
| `tests/test_upload_limits.py` | 4 | File size limits, list length caps |
| `tests/test_cors.py` | 5 | CORS config property parsing |
| `tests/test_search_health_leak.py` | 4 | LRU eviction, cap enforcement |

All 25 tests (18 new + 7 existing regression) pass.

## Journey Log

- [lesson] Monkeypatching `backend.config.settings` doesn't affect modules that did `from backend.config import settings` at import time — must monkeypatch the consuming module's binding instead
- [lesson] CORS middleware is configured at app startup; cannot be changed via monkeypatch in tests — test the config property instead
- [pivot] Upload guard uses lazy import (`_get_settings()`) to enable test monkeypatching of settings
