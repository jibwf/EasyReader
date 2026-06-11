import json
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.models.book import SearchResultItem
from backend.services.search import search_books_stream_v2

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(
    keyword: str = Query(..., min_length=1),
    mode: Literal["fast", "full"] = Query(default="fast"),
    sources: str | None = Query(None, description="Comma-separated source URLs"),
    stream: bool = Query(default=True, description="Use SSE stream when true, return final JSON snapshot when false"),
):
    source_urls = [s.strip() for s in sources.split(",") if s.strip()] if sources else None

    if not stream:
        last_snapshot: list[SearchResultItem] = []
        async for batch in search_books_stream_v2(keyword, source_urls=source_urls, mode=mode):
            last_snapshot = batch
        return [item.model_dump() for item in last_snapshot]

    async def event_stream():
        async for batch in search_books_stream_v2(keyword, source_urls=source_urls, mode=mode):
            data = json.dumps([item.model_dump() for item in batch], ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
