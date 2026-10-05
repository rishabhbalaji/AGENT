import unittest
from datetime import datetime, timedelta, timezone

from job_engine.ats import NormalizedPosting
from job_engine.normalization import (
    ExpirationState,
    canonicalize_url,
    deduplicate_postings,
    normalize_posting,
    stable_posting_id,
)


AT = datetime(2026, 2, 1, tzinfo=timezone.utc)


def posting(**overrides):
    values = {
        "source_name": "fixture_source",
        "source_job_id": "job-1",
        "title": "Python Developer",
        "company": "Example Ltd",
        "source_url": "https://jobs.example/jobs/job-1",
        "description": "Build tested Python tools.",
        "raw_reference": '{"raw":"source"}',
    }
    values.update(overrides)
    return NormalizedPosting(**values)


class NormalizationTests(unittest.TestCase):
    def test_canonicalize_url_removes_tracking_parameters(self):
        self.assertEqual(
            canonicalize_url(
                "HTTPS://Jobs.Example/jobs/1/?utm_source=feed&ref=home&x=1"
            ),
            "https://jobs.example/jobs/1?x=1",
        )

    def test_stable_id_uses_source_identity(self):
        first = stable_posting_id(posting(source_url="https://one.example/job"))
        second = stable_posting_id(posting(source_url="https://two.example/job"))
        self.assertEqual(first, second)

    def test_normalize_preserves_raw_snapshot_and_expiration(self):
        record = normalize_posting(
            posting(
                closes_at=AT + timedelta(days=1),
            ),
            fetched_at=AT,
            at=AT,
        )
        self.assertEqual(record.raw_snapshot, '{"raw":"source"}')
        self.assertEqual(record.expiration, ExpirationState.ACTIVE)
        self.assertEqual(record.duplicate_count, 1)

    def test_expired_and_unknown_states(self):
        expired = normalize_posting(
            posting(closes_at=AT - timedelta(seconds=1)),
            fetched_at=AT,
            at=AT,
        )
        unknown = normalize_posting(posting(), fetched_at=AT, at=AT)
        self.assertEqual(expired.expiration, ExpirationState.EXPIRED)
        self.assertEqual(unknown.expiration, ExpirationState.UNKNOWN)

    def test_deduplicate_keeps_latest_and_marks_repost(self):
        older = normalize_posting(posting(title="Older"), fetched_at=AT)
        newer = normalize_posting(
            posting(title="Newer"),
            fetched_at=AT + timedelta(minutes=1),
        )
        result = deduplicate_postings([older, newer])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].posting.title, "Newer")
        self.assertTrue(result[0].is_repost)
        self.assertEqual(result[0].duplicate_count, 2)

    def test_naive_fetch_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            normalize_posting(posting(), fetched_at=datetime(2026, 1, 1))
