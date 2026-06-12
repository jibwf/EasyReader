from typing import Literal

from pydantic import BaseModel


BackupRestoreMode = Literal["full", "incremental"]
BackupConflictPolicy = Literal["backup_wins", "local_wins", "newer_wins"]


class BackupTableRestoreSummary(BaseModel):
    incoming: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0
    resolved_with_backup: int = 0
    resolved_with_local: int = 0


class BackupFileRestoreSummary(BaseModel):
    incoming: int = 0
    written: int = 0
    skipped: int = 0
    conflicts: int = 0
    resolved_with_backup: int = 0
    resolved_with_local: int = 0


class BackupRestoreResponse(BaseModel):
    ok: bool = True
    format_version: str
    mode: BackupRestoreMode
    conflict_policy: BackupConflictPolicy
    conflicts: int = 0
    tables: dict[str, BackupTableRestoreSummary]
    files: dict[str, BackupFileRestoreSummary]