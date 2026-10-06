"""Read-only checks for unattended engine recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .backups import list_backups
from .database import DatabaseError, migrate
from .worker import pause_status


@dataclass(frozen=True)
class RecoveryCheck:
    name: str
    status: str
    detail: str


def _database_check(database_path: Path) -> RecoveryCheck:
    try:
        migrate(database_path)
        with sqlite3.connect(database_path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            return RecoveryCheck("database_integrity", "failed", str(result[0]))
        return RecoveryCheck("database_integrity", "ok", str(database_path))
    except (DatabaseError, sqlite3.Error) as exc:
        return RecoveryCheck("database_integrity", "failed", str(exc))


def _backup_check(backup_root: Path) -> RecoveryCheck:
    backups = list_backups(backup_root)
    if not backups:
        return RecoveryCheck("backup_available", "warning", "no backups found")
    try:
        with sqlite3.connect(backups[-1]) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            return RecoveryCheck("backup_integrity", "failed", str(result[0]))
        return RecoveryCheck("backup_integrity", "ok", str(backups[-1]))
    except sqlite3.Error as exc:
        return RecoveryCheck("backup_integrity", "failed", str(exc))


def run_recovery_checks(
    database_path: Path,
    backup_root: Path,
    pause_path: Path,
) -> tuple[RecoveryCheck, ...]:
    """Run non-destructive local checks and report pause state."""
    return (
        _database_check(database_path),
        _backup_check(backup_root),
        RecoveryCheck(
            "worker_pause",
            "paused" if pause_status(pause_path) else "running",
            str(pause_path.expanduser()),
        ),
    )
