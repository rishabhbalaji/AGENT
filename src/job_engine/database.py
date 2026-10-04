"""SQLite database initialization and migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path


class DatabaseError(RuntimeError):
    """Raised when database initialization or migration fails."""


Migration = Callable[[sqlite3.Connection], None]


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            description TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered'
                CHECK (status IN (
                    'discovered', 'shortlisted', 'apply_yourself', 'drafted',
                    'parked', 'applied', 'rejected', 'interview', 'archived'
                ))
        );

        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            route TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'drafted',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
        """
    )


MIGRATIONS: tuple[tuple[int, Migration], ...] = ((1, _migration_1),)


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def migrate(database_path: Path) -> int:
    """Apply pending migrations and return the resulting schema version."""
    database_path = database_path.expanduser()
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            _ensure_migration_table(connection)
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            }
            for version, migration in MIGRATIONS:
                if version in applied:
                    continue
                connection.execute("BEGIN")
                try:
                    migration(connection)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations(version, applied_at)
                        VALUES (?, datetime('now'))
                        """,
                        (version,),
                    )
                    connection.commit()
                except sqlite3.Error as exc:
                    connection.rollback()
                    raise DatabaseError(
                        f"migration {version} failed for {database_path}: {exc}"
                    ) from exc
            return max((version for version, _ in MIGRATIONS), default=0)
    except OSError as exc:
        raise DatabaseError(f"cannot prepare database directory: {exc}") from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot open database {database_path}: {exc}") from exc


def record_event(
    database_path: Path,
    event_type: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload_json: str = "{}",
) -> int:
    """Record one event after ensuring the database schema exists."""
    if not event_type.strip():
        raise ValueError("event_type must not be empty")
    migrate(database_path)
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO events(
                    event_type, entity_type, entity_id, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (event_type, entity_type, entity_id, payload_json),
            )
            return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot record event in {database_path}: {exc}") from exc
