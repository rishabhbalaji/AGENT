import unittest
from datetime import datetime, timezone

from job_engine.ats import NormalizedPosting
from job_engine.claims import Claim, validate_claims
from job_engine.documents import DocumentGenerationError, generate_tailored_documents
from job_engine.evidence import EvidenceChunk
from job_engine.normalization import normalize_posting


def posting_record():
    return normalize_posting(
        NormalizedPosting(
            source_name="fixture",
            source_job_id="job-1",
            title="Python Developer",
            company="Example Ltd",
            source_url="https://example.invalid/jobs/1",
            description="Build Python tools.",
        ),
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class DocumentTests(unittest.TestCase):
    def setUp(self):
        evidence = (
            EvidenceChunk("chunk-1", "resume", "/private/resume.pdf#sha256=abc", 0, "Python", "abc"),
        )
        self.claims = validate_claims((Claim("Built Python tools.", ("chunk-1",)),), evidence)

    def test_generates_four_local_review_documents_with_provenance(self):
        packet = generate_tailored_documents(
            posting_record(),
            self.claims,
            ats_answers=(("Why this role?", "I have relevant experience."),),
            linkedin_message="Hello, I am interested in this role.",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(
            tuple(document.document_type for document in packet.documents),
            ("resume", "cover_letter", "ats_answers", "linkedin_message"),
        )
        self.assertTrue(all(document.evidence_ids == ("chunk-1",) for document in packet.documents))
        self.assertIn("Built Python tools.", packet.documents[0].content)

    def test_requires_validated_claims_and_non_empty_ats_values(self):
        with self.assertRaises(DocumentGenerationError):
            generate_tailored_documents(posting_record(), ())
        with self.assertRaises(DocumentGenerationError):
            generate_tailored_documents(
                posting_record(), self.claims, ats_answers=(("", "answer"),)
            )

    def test_rejects_naive_creation_time(self):
        with self.assertRaises(DocumentGenerationError):
            generate_tailored_documents(
                posting_record(),
                self.claims,
                created_at=datetime(2026, 1, 2),
            )


if __name__ == "__main__":
    unittest.main()
