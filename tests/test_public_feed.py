import json
import unittest
from pathlib import Path

from job_engine.ats import SourceHealthStatus
from job_engine.public_feed import GovUkFindAJobAdapter


ROOT = Path(__file__).resolve().parents[1]


class PublicFeedTests(unittest.TestCase):
    def test_govuk_fixture_is_normalized(self):
        payload = json.loads(
            (ROOT / "fixtures" / "govuk_find_a_job.json").read_text(encoding="utf-8")
        )
        adapter = GovUkFindAJobAdapter(
            "https://example.invalid/feed",
            fetcher=lambda url, timeout: (payload, 7),
        )
        result = adapter.fetch()

        self.assertEqual(result.health.status, SourceHealthStatus.HEALTHY)
        self.assertEqual(result.health.records_seen, 1)
        self.assertEqual(result.postings[0].source_job_id, "govuk-fixture-001")
        self.assertEqual(result.postings[0].employment_type, "full_time")

    def test_malformed_feed_is_unavailable(self):
        adapter = GovUkFindAJobAdapter(
            "https://example.invalid/feed",
            fetcher=lambda url, timeout: ({"items": []}, 1),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.UNAVAILABLE)
        self.assertIn("jobs list", result.health.message)

    def test_transport_failure_is_unavailable(self):
        adapter = GovUkFindAJobAdapter(
            "https://example.invalid/feed",
            fetcher=lambda url, timeout: (_ for _ in ()).throw(
                TimeoutError("feed timed out")
            ),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.UNAVAILABLE)
        self.assertIn("feed timed out", result.health.message)

    def test_endpoint_must_be_http(self):
        with self.assertRaises(ValueError):
            GovUkFindAJobAdapter("file:///tmp/feed.json")
