import json
from unittest import TestCase
from unittest.mock import Mock

from job_engine.evidence import EvidenceChunk
from job_engine.model_drafting import draft_with_model
from job_engine.normalization import normalize_posting
from job_engine.ats import NormalizedPosting
from datetime import datetime, timezone


def _posting():
    return normalize_posting(
        NormalizedPosting(
            source_name="fixture",
            source_job_id="draft-1",
            title="Junior Python Developer",
            company="Example Co",
            location="Manchester",
            source_url="https://example.invalid/jobs/draft-1",
            description="Build Python automation.",
            requirements=("Python",),
            clearance_requirements=(),
        ),
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class ModelDraftingTests(TestCase):
    def test_model_claims_are_resolved_before_documents_are_created(self):
        evidence = (
            EvidenceChunk("e1", "resume", "resume.txt", 0, "Built Python automation.", "hash"),
        )
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "claims": [{"text": "Built Python automation.", "evidence_ids": ["e1"]}],
                "ats_answers": [{"question": "Why Python?", "answer": "I build automation."}],
                "linkedin_message": "Hello, I am interested in this role.",
            }
        )

        result = draft_with_model(_posting(), evidence, client)

        self.assertEqual(len(result.documents.documents), 4)
        self.assertEqual(result.provenance.model_version, "sha256:test")
        self.assertIn("e1", result.documents.documents[0].evidence_ids)

    def test_unknown_evidence_fails_closed(self):
        evidence = (
            EvidenceChunk("e1", "resume", "resume.txt", 0, "Built Python automation.", "hash"),
        )
        client = Mock()
        client.config.model = "fixture-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "claims": [{"text": "Invented claim.", "evidence_ids": ["missing"]}],
                "ats_answers": [],
                "linkedin_message": "Hello.",
            }
        )

        with self.assertRaises(ValueError):
            draft_with_model(_posting(), evidence, client)
