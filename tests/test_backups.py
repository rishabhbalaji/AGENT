import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from job_engine.backups import backup_database, list_backups, prune_backups
from job_engine.database import migrate


class BackupTests(TestCase):
    def test_backup_is_readable_and_integrity_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "engine.sqlite3"
            migrate(database)
            backup = backup_database(database, root / "backups")
            with sqlite3.connect(backup) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(len(list_backups(root / "backups")), 1)

    def test_prune_keeps_requested_number(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_root = root / "backups"
            migrate(root / "engine.sqlite3")
            for _ in range(3):
                backup_database(root / "engine.sqlite3", backup_root)
            removed = prune_backups(backup_root, keep=1)
            self.assertEqual(len(removed), 2)
            self.assertEqual(len(list_backups(backup_root)), 1)
