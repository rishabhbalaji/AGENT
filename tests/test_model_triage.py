import json
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock

from job_engine.model_triage import triage_with_model
from job_engine.triage import TriageRecord


def _record(route: str = "draft_for_approval") -> TriageRecord:
    return TriageRecord(
        posting_id="fixture",
        role="Junior Python Developer",
        salary_gbp=None,
        salary_text=None,
        location="Manchester, GB",
        sponsorship="unknown",
        seniority="junior",
        work_mode="hybrid",
        source="fixture",
        source_url="https://example.invalid/jobs/fixture",
        fit_score=80,
        route=route,
        reason_codes=("profile_match",),
        unknowns=(),
        requires_human_approval=True,
    )


class ModelTriageTests(TestCase):
    def test_model_observation_is_validated_and_compared(self) -> None:
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "role": "Junior Python Developer",
                "seniority": "junior",
                "sponsorship": "unknown",
                "clearance_required": False,
                "route": "review",
            }
        )

        comparison = triage_with_model(_record(), client)

        self.assertEqual(comparison.deterministic_route, "draft_for_approval")
        self.assertEqual(comparison.model_route, "review")
        self.assertFalse(comparison.route_matches)
        self.assertEqual(comparison.provenance.model_version, "sha256:test")

    def test_invalid_types_fail_closed(self) -> None:
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "role": "Developer",
                "seniority": "junior",
                "sponsorship": "unknown",
                "clearance_required": "no",
                "route": "review",
            }
        )

        with self.assertRaises(ValueError):
            triage_with_model(_record(), client)

    def test_clearance_record_rejects_non_park_model_route(self) -> None:
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "role": "Python Developer",
                "seniority": "unknown",
                "sponsorship": "unknown",
                "clearance_required": True,
                "route": "review",
            }
        )

        with self.assertRaisesRegex(ValueError, "clearance"):
            triage_with_model(
                replace(_record(route="park"), unknowns=("clearance_required",)),
                client,
            )
