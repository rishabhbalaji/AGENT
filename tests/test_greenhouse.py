import json
import unittest
from pathlib import Path

from job_engine.ats import SourceHealthStatus
from job_engine.greenhouse import GreenhouseAdapter


ROOT = Path(__file__).resolve().parents[1]


class GreenhouseAdapterTests(unittest.TestCase):
    def test_fixture_payload_is_normalized(self):
        payload = json.loads(
            (ROOT / "fixtures" / "greenhouse_jobs.json").read_text(encoding="utf-8")
        )
        adapter = GreenhouseAdapter(
            "example",
            fetcher=lambda url, timeout: (payload, 12),
        )
        result = adapter.fetch()

        self.assertEqual(adapter.url, "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true")
        self.assertEqual(result.health.status, SourceHealthStatus.HEALTHY)
        self.assertEqual(result.health.records_seen, 2)
        self.assertEqual(result.postings[0].source_job_id, "12345")
        self.assertEqual(result.postings[0].company, "Example Systems")
        self.assertEqual(result.postings[0].location, "Manchester, GB")

    def test_transport_failure_is_unavailable(self):
        adapter = GreenhouseAdapter(
            "example",
            fetcher=lambda url, timeout: (_ for _ in ()).throw(
                TimeoutError("timed out")
            ),
        )
        result = adapter.fetch()

        self.assertEqual(result.postings, ())
        self.assertEqual(result.health.status, SourceHealthStatus.UNAVAILABLE)
        self.assertIn("timed out", result.health.message)

    def test_malformed_payload_is_unavailable(self):
        adapter = GreenhouseAdapter(
            "example",
            fetcher=lambda url, timeout: ({"unexpected": []}, 1),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.UNAVAILABLE)
        self.assertIn("jobs list", result.health.message)

    def test_constructor_rejects_invalid_settings(self):
        with self.assertRaises(ValueError):
            GreenhouseAdapter("")
        with self.assertRaises(ValueError):
            GreenhouseAdapter("example", timeout=0)
