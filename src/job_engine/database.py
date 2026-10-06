"""SQLite database initialization and migrations."""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
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


def _migration_2(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE jobs ADD COLUMN fit_score INTEGER NOT NULL DEFAULT 0;

        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            document_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence_ids_json TEXT NOT NULL,
            model TEXT NOT NULL,
            model_version TEXT NOT NULL,
            gate_passed INTEGER NOT NULL CHECK (gate_passed IN (0, 1)),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS repair_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            document_type TEXT NOT NULL,
            gate TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_drafts_job_id ON drafts(job_id);
        CREATE INDEX IF NOT EXISTS idx_repair_queue_job_id ON repair_queue(job_id);
        """
    )


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _migration_1),
    (2, _migration_2),
)


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


def update_job_status(database_path: Path, job_id: str, status: str) -> None:
    """Update one job status and record the human review action."""
    allowed = {
        "apply_yourself",
        "parked",
        "rejected",
        "applied",
    }
    if status not in allowed:
        raise ValueError(f"unsupported review status: {status}")
    application_state = {
        "apply_yourself": ("review", "drafted"),
        "parked": ("park", "parked"),
        "rejected": ("park", "rejected"),
        "applied": ("applied", "applied"),
    }[status]
    migrate(database_path)
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            cursor = connection.execute(
                "UPDATE jobs SET status = ?, last_seen_at = ? WHERE id = ?",
                (status, datetime.now(timezone.utc).isoformat(), job_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise DatabaseError(f"job not found: {job_id}")
            connection.execute(
                """
                UPDATE applications
                SET route = ?, status = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (*application_state, datetime.now(timezone.utc).isoformat(), job_id),
            )
            connection.execute(
                """
                INSERT INTO events(event_type, entity_type, entity_id, payload_json, created_at)
                VALUES (?, 'job', ?, ?, datetime('now'))
                """,
                (
                    f"job_{status}",
                    job_id,
                    json.dumps({"status": status}, sort_keys=True),
                ),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot update job {job_id} in {database_path}: {exc}") from exc


def update_job_text(
    database_path: Path,
    job_id: str,
    *,
    title: str,
    description: str,
) -> None:
    """Edit review-safe job text and record the change."""
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")
    migrate(database_path)
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute(
                "UPDATE jobs SET title = ?, description = ? WHERE id = ?",
                (title, description.strip(), job_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError(f"job not found: {job_id}")
            connection.execute(
                """
                INSERT INTO events(event_type, entity_type, entity_id, payload_json, created_at)
                VALUES ('job_edited', 'job', ?, ?, datetime('now'))
                """,
                (job_id, json.dumps({"title": title}, sort_keys=True)),
            )
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot edit job {job_id} in {database_path}: {exc}") from exc
