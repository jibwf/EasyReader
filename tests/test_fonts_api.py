import asyncio
import hashlib

from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import close_db
from backend.main import app


def _setup_tmp_data(tmp_path):
    asyncio.run(close_db())
    settings.data_dir = tmp_path
    settings.db_path = tmp_path / "reader.db"
    settings.cache_dir = tmp_path / "cache"


def test_fonts_list_and_download(tmp_path):
    _setup_tmp_data(tmp_path)
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    font_bytes = b"dummy-font-data"
    font_name = "NotoSansSC-Regular.ttf"
    font_path = fonts_dir / font_name
    font_path.write_bytes(font_bytes)

    # Unsupported files should not appear in server font list.
    (fonts_dir / "README.txt").write_text("ignore me", encoding="utf-8")

    with TestClient(app) as client:
        response = client.get("/api/fonts")
        assert response.status_code == 200

        body = response.json()
        assert len(body) == 1
        item = body[0]
        assert item["id"] == "NotoSansSC-Regular"
        assert item["name"] == "NotoSansSC-Regular"
        assert item["file_name"] == font_name
        assert item["extension"] == "ttf"
        assert item["size_bytes"] == len(font_bytes)
        assert item["sha256"] == hashlib.sha256(font_bytes).hexdigest()

        download_resp = client.get(item["download_url"])
        assert download_resp.status_code == 200
        assert download_resp.content == font_bytes


def test_font_download_not_found(tmp_path):
    _setup_tmp_data(tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/fonts/not-exists.ttf/download")
        assert response.status_code == 404
        assert response.json()["detail"] == "Font not found"
