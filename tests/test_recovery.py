import tempfile
from pathlib import Path
from unittest import TestCase

from job_engine.backups import backup_database
from job_engine.database import migrate
from job_engine.recovery import run_recovery_checks
from job_engine.worker import set_pause


class RecoveryTests(TestCase):
    def test_checks_report_healthy_database_backup_and_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "engine.sqlite3"
            backups = root / "backups"
            pause = root / "PAUSED"
            migrate(database)
            backup_database(database, backups)
            checks = run_recovery_checks(database, backups, pause)
            self.assertEqual([check.status for check in checks], ["ok", "ok", "running"])

    def test_checks_report_missing_backup_and_paused_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "engine.sqlite3"
            migrate(database)
            pause = root / "PAUSED"
            set_pause(pause)
            checks = run_recovery_checks(database, root / "backups", pause)
            self.assertEqual(checks[1].status, "warning")
            self.assertEqual(checks[2].status, "paused")
