import sqlite3
import tempfile
import unittest
from pathlib import Path

from job_engine.context import ContextAccessError, ReadOnlyContext
from job_engine.database import migrate


class ReadOnlyContextTests(unittest.TestCase):
    def test_reads_allowlisted_jobs_without_mutation_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            migrate(database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        id, title, company, source, source_url,
                        first_seen_at, last_seen_at, fit_score
                    ) VALUES ('job-1', 'Engineer', 'Example', 'fixture',
                              'https://example.test/job-1', 'now', 'now', 90)
                    """
                )
                connection.commit()
            result = ReadOnlyContext(database).read("jobs")
            self.assertEqual(result[0]["id"], "job-1")
            self.assertEqual(result[0]["fit_score"], 90)

    def test_unknown_resource_and_invalid_limit_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ReadOnlyContext(Path(directory) / "engine.sqlite")
            with self.assertRaises(ContextAccessError):
                context.read("applications")
            with self.assertRaises(ContextAccessError):
                context.read("jobs", limit=101)

    def test_missing_database_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContextAccessError, "does not exist"):
                ReadOnlyContext(Path(directory) / "missing.sqlite").read("jobs")
