import unittest

from fastapi.testclient import TestClient

from job_engine.dashboard import (
    DashboardBindingError,
    QueueItem,
    create_dashboard_app,
    validate_bind_host,
)


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


if __name__ == "__main__":
    unittest.main()
