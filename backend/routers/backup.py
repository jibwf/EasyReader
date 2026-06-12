from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from backend.models.backup import BackupConflictPolicy, BackupRestoreMode, BackupRestoreResponse
from backend.services.backup_manager import create_backup_archive, restore_backup_archive

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/export")
async def export_backup():
    file_name, raw_archive = await create_backup_archive()
    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return Response(content=raw_archive, media_type="application/zip", headers=headers)


@router.post("/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    file: UploadFile = File(...),
    mode: BackupRestoreMode = Query(default="incremental"),
    conflict_policy: BackupConflictPolicy = Query(default="backup_wins"),
):
    raw_archive = await file.read()
    if not raw_archive:
        raise HTTPException(status_code=400, detail="Empty backup file")

    try:
        result = await restore_backup_archive(raw_archive, mode, conflict_policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BackupRestoreResponse(**result)