from fastapi import APIRouter, Query

from backend.models.sync import (
    SyncBookmarksBatchRequest,
    SyncBookmarksBatchResponse,
    SyncBookmarksPullResponse,
    SyncProgressItem,
    SyncProgressUpsertRequest,
    SyncPullResponse,
)
from backend.services.sync_manager import pull_bookmarks, pull_progress, upsert_bookmarks_batch, upsert_progress

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/progress/upsert", response_model=SyncProgressItem)
async def upsert_sync_progress(payload: SyncProgressUpsertRequest):
    item = await upsert_progress(payload)
    return SyncProgressItem(**item)


@router.get("/progress/pull", response_model=SyncPullResponse)
async def pull_sync_progress(
    user_id: str = Query(...),
    since: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    result = await pull_progress(user_id=user_id, since=since, limit=limit)
    return SyncPullResponse(**result)


@router.post("/bookmarks/batch", response_model=SyncBookmarksBatchResponse)
async def upsert_sync_bookmarks(payload: SyncBookmarksBatchRequest):
    result = await upsert_bookmarks_batch(payload)
    return SyncBookmarksBatchResponse(**result)


@router.get("/bookmarks/pull", response_model=SyncBookmarksPullResponse)
async def pull_sync_bookmarks(
    user_id: str = Query(...),
    since: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    result = await pull_bookmarks(user_id=user_id, since=since, limit=limit)
    return SyncBookmarksPullResponse(**result)
