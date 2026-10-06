"""Verified local SQLite backups with conservative retention."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .database import DatabaseError, migrate


def backup_database(database_path: Path, backup_root: Path) -> Path:
    """Create and verify an atomic SQLite backup, preserving the source."""
    database_path = database_path.expanduser()
    backup_root = backup_root.expanduser()
    if not database_path.is_file():
        raise DatabaseError(f"database does not exist: {database_path}")
    migrate(database_path)
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_root / f"{database_path.stem}-{stamp}.sqlite3"
    temporary = destination.with_suffix(".sqlite3.tmp")
    try:
        with sqlite3.connect(database_path) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
            target.commit()
            result = target.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise DatabaseError(f"backup integrity check failed: {result[0]}")
        temporary.replace(destination)
        return destination
    except sqlite3.Error as exc:
        temporary.unlink(missing_ok=True)
        raise DatabaseError(f"cannot back up {database_path}: {exc}") from exc
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise DatabaseError(f"cannot finalize backup {destination}: {exc}") from exc


def list_backups(backup_root: Path) -> tuple[Path, ...]:
    """Return backups in chronological filename order."""
    return tuple(sorted(backup_root.expanduser().glob("*.sqlite3")))


def prune_backups(backup_root: Path, *, keep: int) -> tuple[Path, ...]:
    """Remove only surplus generated backups; never touch the source database."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    backups = list_backups(backup_root)
    removed = backups[:-keep]
    for path in removed:
        path.unlink()
    return removed
