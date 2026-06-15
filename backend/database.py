import aiosqlite

from backend.config import settings

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS book_sources (
    book_source_url TEXT PRIMARY KEY,
    book_source_name TEXT NOT NULL,
    book_source_group TEXT DEFAULT '',
    book_source_type INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    source_json TEXT NOT NULL,
    source_format TEXT DEFAULT 'legado',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS book_categories (
    name TEXT PRIMARY KEY,
    hidden INTEGER DEFAULT 0,
    preset INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_key TEXT NOT NULL,
    name TEXT NOT NULL,
    author TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    intro TEXT DEFAULT '',
    book_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    category_name TEXT DEFAULT '网文',
    last_chapter TEXT DEFAULT '',
    total_chapters INTEGER DEFAULT 0,
    media_root TEXT DEFAULT '',
    added_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(book_key)
);

CREATE INDEX IF NOT EXISTS idx_books_category ON books(category_name, updated_at);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    idx INTEGER NOT NULL,
    cached INTEGER DEFAULT 0,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id, idx);

CREATE TABLE IF NOT EXISTS chapter_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_idx INTEGER NOT NULL,
    chapter_title TEXT DEFAULT '',
    chapter_url TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'novel',
    cached_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, chapter_idx)
);

CREATE INDEX IF NOT EXISTS idx_chapter_cache_book ON chapter_cache(book_id, chapter_idx);

CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_progress (
    user_id TEXT NOT NULL,
    book_key TEXT NOT NULL,
    book_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    book_name TEXT DEFAULT '',
    chapter_idx INTEGER DEFAULT 0,
    chapter_title TEXT DEFAULT '',
    chapter_url TEXT DEFAULT '',
    position REAL DEFAULT 0,
    device_id TEXT DEFAULT '',
    updated_at TEXT DEFAULT (datetime('now')),
    revision INTEGER NOT NULL,
    PRIMARY KEY (user_id, book_key)
);

CREATE INDEX IF NOT EXISTS idx_sync_progress_user_revision ON sync_progress(user_id, revision);

CREATE TABLE IF NOT EXISTS sync_bookmarks (
    user_id TEXT NOT NULL,
    bookmark_id TEXT NOT NULL,
    book_key TEXT NOT NULL,
    book_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    book_name TEXT DEFAULT '',
    chapter_idx INTEGER DEFAULT 0,
    chapter_title TEXT DEFAULT '',
    chapter_url TEXT DEFAULT '',
    position REAL DEFAULT 0,
    quote_text TEXT DEFAULT '',
    note TEXT DEFAULT '',
    device_id TEXT DEFAULT '',
    deleted INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    revision INTEGER NOT NULL,
    PRIMARY KEY (user_id, bookmark_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_bookmarks_user_revision ON sync_bookmarks(user_id, revision);

CREATE TABLE IF NOT EXISTS offline_download_tasks (
    task_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    book_id INTEGER NOT NULL,
    book_key TEXT NOT NULL,
    book_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    total_chapters INTEGER DEFAULT 0,
    cached_chapters INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT DEFAULT '',
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_offline_tasks_user ON offline_download_tasks(user_id, device_id, created_at);

CREATE TABLE IF NOT EXISTS offline_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    book_id INTEGER NOT NULL,
    book_key TEXT NOT NULL,
    book_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    name TEXT NOT NULL,
    author TEXT DEFAULT '',
    total_chapters INTEGER DEFAULT 0,
    cached_chapters INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, device_id, book_key),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_offline_catalog_user ON offline_catalog(user_id, device_id, updated_at);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token TEXT PRIMARY KEY,
    device_name TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_used_at TEXT DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(str(settings.database_path))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.executescript(SCHEMA)
        await _ensure_media_root_column(_db)
        await _ensure_default_book_categories(_db)
        await _db.commit()
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


async def _ensure_default_book_categories(db: aiosqlite.Connection):
    await db.execute(
        """INSERT OR IGNORE INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        VALUES ('网文', 0, 1, datetime('now'), datetime('now'))"""
    )
    await db.execute(
        """INSERT OR IGNORE INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        VALUES ('出版', 0, 1, datetime('now'), datetime('now'))"""
    )
    await db.execute(
        """INSERT OR IGNORE INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        VALUES ('有声书', 0, 1, datetime('now'), datetime('now'))"""
    )

    await db.execute("UPDATE book_categories SET preset = 1 WHERE name IN ('网文', '出版', '有声书')")

    await db.execute(
        "UPDATE books SET category_name = '网文' WHERE category_name IS NULL OR TRIM(category_name) = ''"
    )
    await db.execute(
        """INSERT OR IGNORE INTO book_categories
        (name, hidden, preset, created_at, updated_at)
        SELECT DISTINCT category_name, 0, 0, datetime('now'), datetime('now')
        FROM books
        WHERE category_name IS NOT NULL AND TRIM(category_name) <> ''"""
    )


async def _ensure_media_root_column(db: aiosqlite.Connection):
    cursor = await db.execute("PRAGMA table_info(books)")
    columns = {row["name"] for row in await cursor.fetchall()}
    if "media_root" not in columns:
        await db.execute("ALTER TABLE books ADD COLUMN media_root TEXT DEFAULT ''")
