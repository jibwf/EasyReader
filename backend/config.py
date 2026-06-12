from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("data")
    db_path: Path | None = None
    cache_dir: Path | None = None
    log_level: str = "INFO"
    proxy: str | None = None
    request_timeout: int = 15
    max_concurrent_requests: int = 10
    offline_task_worker_enabled: bool = True
    api_key: str = ""  # Empty = auth disabled (backward compatible)
    max_upload_size_mb: int = 200
    cors_origins: str = "*"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    model_config = {"env_prefix": "READER_", "env_file": ".env"}

    @property
    def database_path(self) -> Path:
        if self.db_path:
            return self.db_path
        return self.data_dir / "reader.db"

    @property
    def content_cache_dir(self) -> Path:
        base = self.cache_dir or (self.data_dir / "cache")
        return base / "content"

    @property
    def image_cache_dir(self) -> Path:
        base = self.cache_dir or (self.data_dir / "cache")
        return base / "images"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def font_dir(self) -> Path:
        return self.data_dir / "fonts"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
