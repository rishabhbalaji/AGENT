import unittest

from job_engine.claims import Claim, ClaimValidationError, validate_claims
from job_engine.evidence import EvidenceChunk


def evidence(chunk_id="chunk-1"):
    return EvidenceChunk(chunk_id, "resume", "/private/resume.pdf#sha256=abc", 0, "Python", "abc")


class ClaimValidationTests(unittest.TestCase):
    def test_valid_claim_resolves_evidence(self):
        result = validate_claims((Claim("Built Python tools", ("chunk-1",)),), (evidence(),))
        self.assertEqual(result[0].evidence[0].chunk_id, "chunk-1")
        self.assertEqual(result[0].text, "Built Python tools")

    def test_missing_evidence_is_rejected(self):
        with self.assertRaisesRegex(ClaimValidationError, "lacks evidence"):
            validate_claims((Claim("Built Python tools", ()),), (evidence(),))

    def test_unknown_or_repeated_evidence_is_rejected(self):
        with self.assertRaisesRegex(ClaimValidationError, "unknown evidence"):
            validate_claims((Claim("Built Python tools", ("missing",)),), (evidence(),))
        with self.assertRaisesRegex(ClaimValidationError, "repeats evidence"):
            validate_claims((Claim("Built Python tools", ("chunk-1", "chunk-1")),), (evidence(),))
