import unittest

from fastapi.testclient import TestClient

from job_engine.dashboard import QueueItem, create_dashboard_app


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


if __name__ == "__main__":
    unittest.main()
