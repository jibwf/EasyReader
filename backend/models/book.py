from typing import Literal

from pydantic import BaseModel, Field, field_validator


DEFAULT_BOOK_CATEGORY_NAME = "网文"
PUBLISHED_BOOK_CATEGORY_NAME = "出版"


def _normalize_category_name(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise ValueError("Category name cannot be empty")
    return normalized


class BookSchema(BaseModel):
    id: int | None = None
    book_key: str = ""
    name: str
    author: str = ""
    cover_url: str = ""
    intro: str = ""
    book_url: str
    source_url: str
    category_name: str = DEFAULT_BOOK_CATEGORY_NAME
    last_chapter: str = ""
    total_chapters: int = 0
    added_at: str = ""
    updated_at: str = ""


class ChapterSchema(BaseModel):
    id: int | None = None
    book_id: int
    book_key: str = ""
    title: str
    url: str
    idx: int
    cached: bool = False


class SearchResultItem(BaseModel):
    book_key: str = ""
    name: str
    author: str = ""
    cover_url: str = ""
    intro: str = ""
    book_url: str
    source_url: str
    source_name: str = ""
    last_chapter: str = ""
    kind: str = ""


class BatchBookIdsSchema(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BatchExportSchema(BaseModel):
    ids: list[int] = Field(default_factory=list)
    format: Literal["txt", "epub"]


class CacheClearSchema(BaseModel):
    ids: list[int] = Field(default_factory=list)
    clear_all: bool = False


class BookImportItemSchema(BaseModel):
    name: str
    author: str = ""
    cover_url: str = ""
    intro: str = ""
    book_url: str
    source_url: str


class BookCategorySchema(BaseModel):
    name: str
    hidden: bool = False
    preset: bool = False
    book_count: int = 0


class BookCategoryCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class BookCategoryHiddenSchema(BaseModel):
    hidden: bool


class BookCategoryRenameSchema(BaseModel):
    new_name: str = Field(min_length=1, max_length=32)

    @field_validator("new_name")
    @classmethod
    def validate_new_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class BookCategoryAssignSchema(BaseModel):
    category_name: str = Field(min_length=1, max_length=32)

    @field_validator("category_name")
    @classmethod
    def validate_category_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class BatchBookCategoryAssignSchema(BaseModel):
    ids: list[int] = Field(default_factory=list)
    category_name: str = Field(min_length=1, max_length=32)

    @field_validator("category_name")
    @classmethod
    def validate_category_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class ExportResultItemSchema(BaseModel):
    book_id: int
    name: str
    format: str
    file_name: str
    download_url: str
