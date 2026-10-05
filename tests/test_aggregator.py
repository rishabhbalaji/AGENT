import json
import unittest
from pathlib import Path

from job_engine.aggregator import GuestAggregatorAdapter
from job_engine.ats import SourceHealthStatus


ROOT = Path(__file__).resolve().parents[1]


class GuestAggregatorTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(
            (ROOT / "fixtures" / "guest_aggregator.json").read_text(encoding="utf-8")
        )
        self.fetcher = lambda url, timeout: (self.payload, 4)

    def test_disabled_by_default_without_transport(self):
        adapter = GuestAggregatorAdapter("https://guest.example/feed")
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.DISABLED)
        self.assertIn("disabled", result.health.message)

    def test_allowlist_is_required_before_fetch(self):
        adapter = GuestAggregatorAdapter(
            "https://guest.example/feed",
            enabled=True,
            fetcher=self.fetcher,
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.DISABLED)
        self.assertIn("allowlist", result.health.message)

    def test_approved_fixture_host_can_be_fetched(self):
        adapter = GuestAggregatorAdapter(
            "https://guest.example/feed",
            allowed_hosts=frozenset({"guest.example"}),
            enabled=True,
            fetcher=self.fetcher,
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.HEALTHY)
        self.assertEqual(result.postings[0].source_job_id, "guest-fixture-001")

    def test_transport_failure_is_unavailable(self):
        adapter = GuestAggregatorAdapter(
            "https://guest.example/feed",
            allowed_hosts=frozenset({"guest.example"}),
            enabled=True,
            fetcher=lambda url, timeout: (_ for _ in ()).throw(
                TimeoutError("guest feed timed out")
            ),
        )
        result = adapter.fetch()
        self.assertEqual(result.health.status, SourceHealthStatus.UNAVAILABLE)

    def test_http_endpoint_is_allowed_only_when_explicit(self):
        adapter = GuestAggregatorAdapter(
            "http://guest.example/feed",
            allowed_hosts=frozenset({"guest.example"}),
            enabled=True,
            fetcher=self.fetcher,
        )
        self.assertEqual(adapter.fetch().health.status, SourceHealthStatus.HEALTHY)
