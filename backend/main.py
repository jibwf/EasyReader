from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import close_db, get_db
from backend.routers import auth, backup, books, content, explore, fonts, offline, proxy, search, sources, sync
from backend.services.sync_manager import bootstrap_offline_task_worker, shutdown_offline_task_worker

VERSION_PATTERN = re.compile(r"^\d{8}\d+$")
API_CONTRACT_VERSION = "2026-06-11"
SUPPORTED_CLIENT_TYPES = ["web-pwa", "eink-android"]


def normalize_version(value: str) -> str:
    cleaned = value.strip()
    if VERSION_PATTERN.match(cleaned):
        return cleaned
    return f"{datetime.now().strftime('%Y%m%d')}1"


def read_server_version() -> str:
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return normalize_version(version_file.read_text())
    return f"{datetime.now().strftime('%Y%m%d')}1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db()
    await bootstrap_offline_task_worker()
    yield
    await shutdown_offline_task_worker()
    await close_db()


app = FastAPI(
    title="EasyReader",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.api_key else "/docs",
    redoc_url="/redoc" if settings.api_key else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_api_auth(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    public_paths = ["/api/version", "/api/auth/login", "/api/auth/verify"]
    if request.url.path in public_paths:
        return await call_next(request)

    from backend.config import settings
    if not settings.api_key and not settings.password:
        return await call_next(request)

    if settings.api_key:
        provided_key = request.headers.get("x-api-key", "")
        if provided_key == settings.api_key:
            return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        from backend.services.auth import verify_token
        if await verify_token(token):
            return await call_next(request)

    return JSONResponse(status_code=401, content={"detail": "Invalid or missing authentication"})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Server-Version"] = read_server_version()
        response.headers["X-API-Contract-Version"] = API_CONTRACT_VERSION
        response.headers["X-Supported-Client-Types"] = ",".join(SUPPORTED_CLIENT_TYPES)
    return response


app.include_router(auth.router)
app.include_router(sources.router)
app.include_router(search.router)
app.include_router(content.router)
app.include_router(books.router)
app.include_router(explore.router)
app.include_router(proxy.router)
app.include_router(sync.router)
app.include_router(offline.router)
app.include_router(fonts.router)
app.include_router(backup.router)

@app.get("/api/version")
async def get_version():
    return {
        "version": read_server_version(),
        "api_contract_version": API_CONTRACT_VERSION,
        "supported_client_types": SUPPORTED_CLIENT_TYPES,
    }

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        # Serve static file if it exists, otherwise return index.html for SPA routing
        file_path = static_dir / path
        if path and file_path.exists() and file_path.is_file():
            response = FileResponse(file_path)
        else:
            response = FileResponse(static_dir / "index.html")
        if path in ("", "index.html", "reader-sw.js", "sw.js", "registerSW.js", "manifest.webmanifest"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response
