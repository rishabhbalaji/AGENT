import json
import unittest
from pathlib import Path

from job_engine.ats import SourceHealthStatus
from job_engine.public_feed import AdzunaAdapter, GovUkFindAJobAdapter, ReedAdapter


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

    def test_reed_requires_explicit_api_key(self):
        result = ReedAdapter(keywords="graduate Python").fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.DISABLED)
        self.assertIn("API key", result.health.message)

    def test_reed_fixture_is_normalized(self):
        payload = json.loads(
            (ROOT / "fixtures" / "reed_jobs.json").read_text(encoding="utf-8")
        )
        adapter = ReedAdapter(
            api_key="fixture-key",
            keywords="graduate Python",
            fetcher=lambda url, timeout: (payload, 9),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.HEALTHY)
        self.assertEqual(result.postings[0].source_job_id, "reed-fixture-001")
        self.assertEqual(result.postings[0].company, "Example Systems")

    def test_adzuna_requires_both_credentials(self):
        result = AdzunaAdapter().fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.DISABLED)
        self.assertIn("app_id", result.health.message)

    def test_adzuna_fixture_is_normalized(self):
        payload = json.loads(
            (ROOT / "fixtures" / "adzuna_jobs.json").read_text(encoding="utf-8")
        )
        adapter = AdzunaAdapter(
            app_id="fixture-id",
            app_key="fixture-key",
            keywords="graduate Python",
            fetcher=lambda url, timeout: (payload, 11),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.HEALTHY)
        self.assertEqual(result.postings[0].source_job_id, "adzuna-fixture-001")
        self.assertEqual(result.postings[0].location, "Manchester")
