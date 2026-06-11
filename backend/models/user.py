from pydantic import BaseModel


class ReadingProgressSchema(BaseModel):
    book_id: int
    chapter_idx: int = 0
    scroll_position: float = 0.0
    updated_at: str = ""


class UserSettingSchema(BaseModel):
    key: str
    value: str
