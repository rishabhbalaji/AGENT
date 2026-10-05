import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3

from fastapi.testclient import TestClient

from job_engine.dashboard import (
    DashboardBindingError,
    QueueItem,
    create_dashboard_app,
    queues_from_database,
    validate_bind_host,
)
from job_engine.database import migrate


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_dashboard_app(
                {
                    "drafts": (
                        QueueItem("job-1", "Python Developer", "Example Ltd", "Review me"),
                    )
                }
            )
        )

    def test_home_lists_review_queues_and_non_submission_notice(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("apply-yourself", response.text)
        self.assertIn("does not submit applications", response.text)

    def test_queue_renders_items_with_escaped_content(self):
        response = self.client.get("/queue/drafts")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Python Developer", response.text)
        self.assertIn("Review me", response.text)

    def test_unknown_queue_is_not_found(self):
        response = self.client.get("/queue/unknown")
        self.assertEqual(response.status_code, 404)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Dashboard healthy", response.text)

    def test_bind_host_allows_loopback_and_tailscale_addresses(self):
        self.assertEqual(validate_bind_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(validate_bind_host("100.101.102.103"), "100.101.102.103")

    def test_bind_host_rejects_wildcard_and_public_addresses(self):
        for host in ("0.0.0.0", "::", "192.168.1.10", "example.com", ""):
            with self.subTest(host=host):
                with self.assertRaises(DashboardBindingError):
                    validate_bind_host(host)

    def test_queues_are_loaded_from_persisted_job_statuses(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite3"
            migrate(database)
            with sqlite3.connect(database) as connection:
                connection.executemany(
                    """
                    INSERT INTO jobs(
                        id, title, company, location, source, source_url,
                        description, first_seen_at, last_seen_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            "job-applied",
                            "Applied role",
                            "Example",
                            None,
                            "fixture",
                            "https://example.invalid/applied",
                            "Applied summary",
                            "2026-01-01",
                            "2026-01-02",
                            "applied",
                        ),
                        (
                            "job-draft",
                            "Draft role",
                            "Example",
                            None,
                            "fixture",
                            "https://example.invalid/draft",
                            "Draft summary",
                            "2026-01-01",
                            "2026-01-03",
                            "drafted",
                        ),
                        (
                            "job-review",
                            "Review role",
                            "Example",
                            None,
                            "fixture",
                            "https://example.invalid/review",
                            "Review summary",
                            "2026-01-01",
                            "2026-01-01",
                            "discovered",
                        ),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO applications(
                        id, job_id, route, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "application-review",
                        "job-review",
                        "review",
                        "drafted",
                        "2026-01-01",
                        "2026-01-01",
                    ),
                )
            queues = queues_from_database(database)
            self.assertEqual(queues["applied"][0].job_id, "job-applied")
            self.assertEqual(queues["drafts"][0].title, "Draft role")
            self.assertEqual(queues["apply-yourself"][0].job_id, "job-review")
            self.assertEqual(queues["parked"], ())


if __name__ == "__main__":
    unittest.main()
