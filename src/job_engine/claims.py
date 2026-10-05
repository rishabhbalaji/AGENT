"""Evidence-backed claim validation for generated application material."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .evidence import EvidenceChunk


class ClaimValidationError(ValueError):
    """Raised when a claim is malformed or lacks supporting evidence."""


@dataclass(frozen=True)
class Claim:
    """A factual statement that must cite one or more local evidence chunks."""

    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedClaim:
    """A claim accepted with resolved evidence provenance."""

    text: str
    evidence: tuple[EvidenceChunk, ...]


def validate_claims(
    claims: Iterable[Claim],
    evidence: Iterable[EvidenceChunk],
) -> tuple[ValidatedClaim, ...]:
    """Reject unsupported claims and return claims with resolved evidence."""
    evidence_by_id = {chunk.chunk_id: chunk for chunk in evidence}
    validated: list[ValidatedClaim] = []
    for claim in claims:
        if not isinstance(claim, Claim) or not claim.text.strip():
            raise ClaimValidationError("claim text must be non-empty")
        if not claim.evidence_ids:
            raise ClaimValidationError(f"claim lacks evidence: {claim.text}")
        if len(set(claim.evidence_ids)) != len(claim.evidence_ids):
            raise ClaimValidationError(f"claim repeats evidence IDs: {claim.text}")
        try:
            supporting = tuple(evidence_by_id[evidence_id] for evidence_id in claim.evidence_ids)
        except KeyError as exc:
            raise ClaimValidationError(
                f"claim references unknown evidence: {claim.text}"
            ) from exc
        validated.append(ValidatedClaim(claim.text.strip(), supporting))
    return tuple(validated)
