import sqlite3
import tempfile
import unittest
from pathlib import Path

from job_engine.database import DatabaseError, migrate, record_event


class DatabaseTests(unittest.TestCase):
    def test_migrate_creates_schema_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "data" / "engine.sqlite"
            self.assertEqual(migrate(database), 2)
            self.assertEqual(migrate(database), 2)
            with sqlite3.connect(database) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                versions = list(
                    connection.execute("SELECT version FROM schema_migrations")
                )
        self.assertTrue({"jobs", "applications", "events"}.issubset(tables))
        self.assertEqual(versions, [(1,), (2,)])

    def test_record_event_returns_id_and_persists_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            event_id = record_event(
                database,
                "health_check",
                entity_type="runtime",
                entity_id="local",
                payload_json='{"status":"ok"}',
            )
            with sqlite3.connect(database) as connection:
                row = connection.execute(
                    """
                    SELECT event_type, entity_type, entity_id, payload_json
                    FROM events WHERE id = ?
                    """,
                    (event_id,),
                ).fetchone()
        self.assertEqual(
            row,
            ("health_check", "runtime", "local", '{"status":"ok"}'),
        )

    def test_empty_event_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "event_type"):
                record_event(Path(directory) / "engine.sqlite", " ")

    def test_failed_database_path_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "not-a-directory"
            parent.write_text("occupied", encoding="utf-8")
            with self.assertRaises(DatabaseError):
                migrate(parent / "engine.sqlite")
