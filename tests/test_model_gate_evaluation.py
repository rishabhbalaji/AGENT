import json
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock

from job_engine.ats import NormalizedPosting
from job_engine.evidence import EvidenceChunk
from job_engine.model_gate_evaluation import evaluate_model_draft
from job_engine.normalization import normalize_posting


def _posting():
    return normalize_posting(
        NormalizedPosting(
            source_name="fixture",
            source_job_id="gate-1",
            title="Python Developer",
            company="Example Co",
            source_url="https://example.invalid/jobs/gate-1",
            description="Build Python tools.",
        ),
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class ModelGateEvaluationTests(TestCase):
    def test_passing_model_draft_passes_document_gates(self):
        evidence = (
            EvidenceChunk("e1", "resume", "resume.txt", 0, "Built Python tools.", "hash"),
        )
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "claims": [{"text": "Built Python tools.", "evidence_ids": ["e1"]}],
                "ats_answers": [{"question": "Why Python?", "answer": "I build tools."}],
                "linkedin_message": "Hello, I am interested.",
            }
        )

        result = evaluate_model_draft(_posting(), evidence, client)

        self.assertEqual(result.drafting_status, "passed")
        self.assertTrue(result.gates_passed)
        self.assertEqual(result.repair_count, 0)
        self.assertEqual(result.digest, "sha256:test")

    def test_unsupported_claim_fails_closed(self):
        evidence = (
            EvidenceChunk("e1", "resume", "resume.txt", 0, "Built Python tools.", "hash"),
        )
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "claims": [{"text": "Managed a global team.", "evidence_ids": ["missing"]}],
                "ats_answers": [],
                "linkedin_message": "Hello.",
            }
        )

        result = evaluate_model_draft(_posting(), evidence, client)

        self.assertEqual(result.drafting_status, "failed")
        self.assertFalse(result.gates_passed)
        self.assertIn("unknown evidence", result.error)
