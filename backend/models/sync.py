from typing import Literal

from pydantic import BaseModel, Field


class SyncProgressUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    book_key: str = Field(min_length=1)
    book_url: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    book_name: str = ""
    chapter_idx: int = 0
    chapter_title: str = ""
    chapter_url: str = ""
    position: float = 0.0
    force: bool = False


class SyncProgressItem(BaseModel):
    user_id: str
    device_id: str
    book_key: str
    book_url: str
    source_url: str
    book_name: str
    chapter_idx: int
    chapter_title: str
    chapter_url: str
    position: float
    revision: int
    updated_at: str
    accepted: bool = True
    conflict: bool = False
    conflict_reason: str = ""


class SyncPullResponse(BaseModel):
    items: list[SyncProgressItem]
    next_cursor: int


class SyncBookmarkUpsertItem(BaseModel):
    bookmark_id: str = Field(min_length=1)
    book_key: str = Field(min_length=1)
    book_url: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    book_name: str = ""
    chapter_idx: int = 0
    chapter_title: str = ""
    chapter_url: str = ""
    position: float = 0.0
    quote_text: str = ""
    note: str = ""
    deleted: bool = False


class SyncBookmarksBatchRequest(BaseModel):
    user_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    items: list[SyncBookmarkUpsertItem] = Field(default_factory=list)


class SyncBookmarkItem(BaseModel):
    user_id: str
    device_id: str
    bookmark_id: str
    book_key: str
    book_url: str
    source_url: str
    book_name: str
    chapter_idx: int
    chapter_title: str
    chapter_url: str
    position: float
    quote_text: str
    note: str
    deleted: bool
    revision: int
    updated_at: str


class SyncBookmarksBatchResponse(BaseModel):
    items: list[SyncBookmarkItem]
    next_cursor: int


class SyncBookmarksPullResponse(BaseModel):
    items: list[SyncBookmarkItem]
    next_cursor: int


class OfflineTaskCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    book_id: int | None = None
    book_key: str | None = None
    book_url: str | None = None
    source_url: str | None = None


class OfflineTaskItem(BaseModel):
    task_id: str
    user_id: str
    device_id: str
    book_id: int
    book_key: str
    book_name: str = ""
    book_url: str
    source_url: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = 0
    total_chapters: int
    cached_chapters: int
    error_message: str = ""
    created_at: str
    updated_at: str
    completed_at: str = ""


class OfflineCatalogItem(BaseModel):
    user_id: str
    device_id: str
    book_id: int
    book_key: str
    book_url: str
    source_url: str
    name: str
    author: str
    total_chapters: int
    cached_chapters: int
    updated_at: str
