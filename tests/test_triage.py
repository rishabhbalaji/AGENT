import unittest
from datetime import datetime, timezone

from job_engine.ats import NormalizedPosting
from job_engine.matching import MatchDecision
from job_engine.normalization import normalize_posting
from job_engine.triage import triage_posting


def record(**overrides):
    values = {
        "source_name": "greenhouse",
        "source_job_id": "job-1",
        "title": "Senior Python Developer",
        "company": "Example Ltd",
        "source_url": "https://example.invalid/jobs/1",
        "description": "Hybrid role with visa sponsorship available.",
        "location": "Manchester, GB",
        "remote_mode": "hybrid",
        "metadata": {
            "salary_gbp": "55000",
            "salary_text": "£50,000-£55,000",
        },
    }
    values.update(overrides)
    posting = NormalizedPosting(**values)
    return normalize_posting(
        posting,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


class TriageTests(unittest.TestCase):
    def test_matched_posting_is_structured_and_requires_approval(self):
        decision = MatchDecision(
            "full_time",
            85,
            70,
            True,
            False,
            ("location_match",),
            (),
        )
        triage = triage_posting(record(), decision)
        self.assertEqual(triage.role, "Senior Python Developer")
        self.assertEqual(triage.salary_gbp, 55000)
        self.assertEqual(triage.salary_text, "£50,000-£55,000")
        self.assertEqual(triage.sponsorship, "available")
        self.assertEqual(triage.seniority, "senior")
        self.assertEqual(triage.work_mode, "hybrid")
        self.assertEqual(triage.route, "draft_for_approval")
        self.assertTrue(triage.requires_human_approval)
        self.assertIn("profile_match", triage.reason_codes)

    def test_excluded_posting_is_parked_without_approval(self):
        decision = MatchDecision(
            "full_time",
            0,
            70,
            False,
            True,
            ("clearance_exclusion:sc",),
            (),
        )
        triage = triage_posting(record(), decision)
        self.assertEqual(triage.route, "park")
        self.assertFalse(triage.requires_human_approval)

    def test_missing_fields_are_explicit(self):
        triage = triage_posting(
            record(
                title="Developer",
                description="Build software.",
                location=None,
                remote_mode=None,
                metadata={},
            ),
            MatchDecision("full_time", 20, 70, False, False, (), ()),
        )
        self.assertEqual(triage.sponsorship, "unknown")
        self.assertEqual(triage.seniority, "unknown")
        self.assertEqual(triage.work_mode, "unknown")
        self.assertIn("salary_missing", triage.unknowns)
        self.assertIn("location_missing", triage.unknowns)
        self.assertIn("sponsorship_missing", triage.unknowns)

    def test_below_threshold_uses_review_route(self):
        triage = triage_posting(
            record(),
            MatchDecision("full_time", 60, 70, False, False, ("below_score_threshold",), ()),
        )
        self.assertEqual(triage.route, "review")
        self.assertTrue(triage.requires_human_approval)


if __name__ == "__main__":
    unittest.main()
