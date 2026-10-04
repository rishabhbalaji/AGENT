import unittest
from datetime import datetime, timezone

from job_engine.ats import (
    NormalizedPosting,
    RateLimit,
    SourceContractError,
    SourceFetchResult,
    SourceHealth,
    SourceHealthStatus,
)


def posting(**overrides):
    values = {
        "source_name": "fixture_source",
        "source_job_id": "job-1",
        "title": "Python Developer",
        "company": "Example Ltd",
        "source_url": "https://example.invalid/jobs/job-1",
        "description": "Build tested Python tools.",
    }
    values.update(overrides)
    return NormalizedPosting(**values)


class AtsContractTests(unittest.TestCase):
    def test_normalized_posting_accepts_public_job(self):
        result = posting(
            requirements=("Python",),
            clearance_requirements=("None",),
        )
        self.assertEqual(result.source_job_id, "job-1")
        self.assertEqual(result.requirements, ("Python",))

    def test_posting_rejects_invalid_url(self):
        with self.assertRaisesRegex(SourceContractError, "source_url"):
            posting(source_url="not-a-url")

    def test_posting_rejects_naive_dates_and_reversed_window(self):
        with self.assertRaisesRegex(SourceContractError, "posted_at"):
            posting(posted_at=datetime(2026, 1, 1))
        with self.assertRaisesRegex(SourceContractError, "closes_at"):
            posting(
                posted_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                closes_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_rate_limit_requires_positive_values(self):
        with self.assertRaises(SourceContractError):
            RateLimit(0)
        with self.assertRaises(SourceContractError):
            RateLimit(10, burst=0)

    def test_source_health_requires_aware_timestamp(self):
        with self.assertRaisesRegex(SourceContractError, "checked_at"):
            SourceHealth("source", SourceHealthStatus.HEALTHY, datetime(2026, 1, 1))

    def test_fetch_result_keeps_postings_and_health_aligned(self):
        checked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        health = SourceHealth(
            "fixture_source",
            SourceHealthStatus.HEALTHY,
            checked_at,
            records_seen=1,
        )
        result = SourceFetchResult((posting(),), health, checked_at)
        self.assertEqual(result.health.records_seen, 1)

    def test_fetch_result_rejects_mixed_sources(self):
        checked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        health = SourceHealth(
            "other_source", SourceHealthStatus.HEALTHY, checked_at
        )
        with self.assertRaisesRegex(SourceContractError, "belong"):
            SourceFetchResult((posting(),), health, checked_at)
