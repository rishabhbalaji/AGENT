import unittest
from datetime import datetime, timezone

from job_engine.ats import NormalizedPosting
from job_engine.claims import Claim, validate_claims
from job_engine.document_gates import run_document_gates
from job_engine.documents import DocumentDraft, TailoredDocuments
from job_engine.evidence import EvidenceChunk
from job_engine.normalization import normalize_posting


def packet():
    posting = normalize_posting(
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
    evidence = EvidenceChunk("chunk-1", "resume", "/private/resume.pdf", 0, "Python", "abc")
    claims = validate_claims((Claim("Built Python tools.", ("chunk-1",)),), (evidence,))
    documents = tuple(
        DocumentDraft(
            document_type,
            document_type,
            "Built Python tools. [evidence: chunk-1]",
            ("chunk-1",),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        for document_type in ("resume", "cover_letter", "ats_answers", "linkedin_message")
    )
    return posting, evidence, TailoredDocuments(posting.stable_id, documents)


class DocumentGateTests(unittest.TestCase):
    def test_valid_packet_passes_without_mutation(self):
        _, evidence, packet_value = packet()
        report = run_document_gates(packet_value, (evidence,))
        self.assertTrue(report.passed)
        self.assertEqual(report.repairs, ())

    def test_unknown_evidence_and_placeholders_create_repairs(self):
        _, evidence, packet_value = packet()
        document = packet_value.documents[0]
        broken = DocumentDraft(
            document.document_type,
            document.title,
            "TODO [insert evidence]",
            ("unknown",),
            document.created_at,
        )
        broken_packet = TailoredDocuments(
            packet_value.posting_id,
            (broken, *packet_value.documents[1:]),
        )
        report = run_document_gates(broken_packet, (evidence,))
        self.assertFalse(report.passed)
        self.assertTrue(any(item.gate == "fact" for item in report.repairs))
        self.assertTrue(any(item.gate == "ats" for item in report.repairs))

    def test_missing_ats_answers_are_repaired(self):
        _, evidence, packet_value = packet()
        documents = tuple(
            DocumentDraft(
                document.document_type,
                document.title,
                "No ATS questions supplied."
                if document.document_type == "ats_answers"
                else document.content,
                document.evidence_ids,
                document.created_at,
            )
            for document in packet_value.documents
        )
        report = run_document_gates(
            TailoredDocuments(packet_value.posting_id, documents),
            (evidence,),
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(item.document_type == "ats_answers" for item in report.repairs))

    def test_missing_required_type_is_reported(self):
        _, evidence, packet_value = packet()
        report = run_document_gates(
            TailoredDocuments(packet_value.posting_id, packet_value.documents[:3]),
            (evidence,),
        )
        self.assertFalse(report.passed)
        self.assertTrue(
            any(
                item.document_type == "linkedin_message" and item.gate == "structure"
                for item in report.repairs
            )
        )


if __name__ == "__main__":
    unittest.main()
