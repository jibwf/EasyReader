import hashlib
from pathlib import Path
from urllib.parse import quote

from backend.config import settings

SUPPORTED_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}

FONT_MEDIA_TYPES = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".ttc": "font/collection",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

FONT_DISPLAY_NAMES = {
    "notosanscjksc-regular": "思源黑体（Noto Sans CJK SC）",
    "notosanscjksc-bold": "思源黑体粗体（Noto Sans CJK SC Bold）",
    "notoserifcjksc-regular": "思源宋体（Noto Serif CJK SC）",
    "notoserifcjksc-bold": "思源宋体粗体（Noto Serif CJK SC Bold）",
    "lxgwwenkai-regular": "霞鹜文楷（LXGW WenKai）",
    "canglesongw05-regular": "仓耳与墨 W05",
}


def ensure_font_dir() -> Path:
    font_dir = settings.font_dir
    font_dir.mkdir(parents=True, exist_ok=True)
    return font_dir


def _sha256_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_supported_font(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_FONT_EXTENSIONS


def _get_font_display_name(stem: str) -> str:
    return FONT_DISPLAY_NAMES.get(stem.lower(), stem)


def list_server_fonts() -> list[dict]:
    font_dir = ensure_font_dir().resolve()
    items: list[dict] = []

    for file_path in sorted(font_dir.iterdir(), key=lambda item: item.name.lower()):
        if not file_path.is_file() or not _is_supported_font(file_path):
            continue

        extension = file_path.suffix.lower().lstrip(".")
        items.append(
            {
                "id": file_path.stem,
                "name": _get_font_display_name(file_path.stem),
                "file_name": file_path.name,
                "extension": extension,
                "size_bytes": file_path.stat().st_size,
                "sha256": _sha256_file(file_path),
                "download_url": f"/api/fonts/{quote(file_path.name, safe='')}/download",
            }
        )

    return items


def get_server_font_file(font_file_name: str) -> Path:
    font_dir = ensure_font_dir().resolve()
    safe_name = Path(font_file_name).name
    if not safe_name:
        raise FileNotFoundError("Invalid font name")

    target = (font_dir / safe_name).resolve()
    if target.parent != font_dir:
        raise FileNotFoundError("Invalid font path")
    if not target.exists() or not target.is_file() or not _is_supported_font(target):
        raise FileNotFoundError("Font not found")

    return target


def get_font_media_type(file_path: Path) -> str:
    return FONT_MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
