from fastapi import APIRouter, Query

from backend.models.sync import (
    OfflineCatalogItem,
    OfflineTaskCreateRequest,
    OfflineTaskItem,
)
from backend.services.sync_manager import (
    create_offline_download_task,
    get_offline_task,
    list_offline_catalog,
    list_offline_tasks,
)

router = APIRouter(prefix="/api/offline", tags=["offline"])


@router.post("/tasks", response_model=OfflineTaskItem)
async def create_task(payload: OfflineTaskCreateRequest):
    task = await create_offline_download_task(payload)
    return OfflineTaskItem(**task)


@router.get("/tasks/{task_id}", response_model=OfflineTaskItem)
async def get_task(task_id: str):
    task = await get_offline_task(task_id)
    return OfflineTaskItem(**task)


@router.get("/tasks", response_model=list[OfflineTaskItem])
async def get_tasks(
    user_id: str = Query(...),
    device_id: str = Query(...),
    limit: int = Query(200, ge=1, le=500),
):
    tasks = await list_offline_tasks(user_id=user_id, device_id=device_id, limit=limit)
    return [OfflineTaskItem(**item) for item in tasks]


@router.get("/catalog", response_model=list[OfflineCatalogItem])
async def get_catalog(
    user_id: str = Query(...),
    device_id: str = Query(...),
):
    items = await list_offline_catalog(user_id=user_id, device_id=device_id)
    return [OfflineCatalogItem(**item) for item in items]
