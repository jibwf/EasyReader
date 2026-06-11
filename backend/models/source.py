from pydantic import BaseModel, Field


class SearchRule(BaseModel):
    bookList: str = ""
    name: str = ""
    author: str = ""
    coverUrl: str = ""
    bookUrl: str = ""
    intro: str = ""
    kind: str = ""
    wordCount: str = ""
    lastChapter: str = ""


class BookInfoRule(BaseModel):
    name: str = ""
    author: str = ""
    coverUrl: str = ""
    intro: str = ""
    tocUrl: str = ""
    kind: str = ""
    wordCount: str = ""
    lastChapter: str = ""


class TocRule(BaseModel):
    chapterList: str = ""
    chapterName: str = ""
    chapterUrl: str = ""
    nextTocUrl: str = ""


class ContentRule(BaseModel):
    content: str = ""
    nextContentUrl: str = ""
    replaceRegex: str = ""


class BookSourceSchema(BaseModel):
    """Legado BookSource JSON schema."""

    bookSourceUrl: str
    bookSourceName: str = ""
    bookSourceGroup: str = ""
    bookSourceType: int = 0
    enabled: bool = True
    enabledExplore: bool = True
    header: str = ""
    loginUrl: str = ""
    bookUrlPattern: str = ""
    searchUrl: str = ""
    exploreUrl: str = ""
    ruleSearch: SearchRule = Field(default_factory=SearchRule)
    ruleBookInfo: BookInfoRule = Field(default_factory=BookInfoRule)
    ruleToc: TocRule = Field(default_factory=TocRule)
    ruleContent: ContentRule = Field(default_factory=ContentRule)

    model_config = {"extra": "allow"}


class BookSourceInDB(BaseModel):
    """Database representation of a book source."""

    book_source_url: str
    book_source_name: str
    book_source_group: str
    book_source_type: int
    enabled: bool
    source_json: str
    created_at: str = ""
    updated_at: str = ""
