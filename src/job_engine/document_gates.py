"""Deterministic fact and ATS gates for local application drafts."""

from __future__ import annotations

from dataclasses import dataclass

from .documents import TailoredDocuments
from .evidence import EvidenceChunk


@dataclass(frozen=True)
class RepairQueueItem:
    """A failed gate that requires explicit repair or human review."""

    posting_id: str
    document_type: str
    gate: str
    reason: str


@dataclass(frozen=True)
class DocumentGateReport:
    """The complete gate result without changing the supplied documents."""

    passed: bool
    repairs: tuple[RepairQueueItem, ...]


PLACEHOLDER_MARKERS = (
    "todo",
    "tbd",
    "[insert",
    "[replace",
    "lorem ipsum",
)
REQUIRED_DOCUMENT_TYPES = frozenset(
    {"resume", "cover_letter", "ats_answers", "linkedin_message"}
)


def _repair(
    packet: TailoredDocuments,
    document_type: str,
    gate: str,
    reason: str,
) -> RepairQueueItem:
    return RepairQueueItem(packet.posting_id, document_type, gate, reason)


def run_document_gates(
    packet: TailoredDocuments,
    evidence: tuple[EvidenceChunk, ...],
    *,
    required_document_types: frozenset[str] = REQUIRED_DOCUMENT_TYPES,
) -> DocumentGateReport:
    """Run fact-reference and ATS-safety checks without mutating a packet."""
    repairs: list[RepairQueueItem] = []
    evidence_ids = {chunk.chunk_id for chunk in evidence}
    seen_types: set[str] = set()

    for document in packet.documents:
        if document.document_type in seen_types:
            repairs.append(
                _repair(packet, document.document_type, "structure", "duplicate document type")
            )
        seen_types.add(document.document_type)
        if not document.content.strip():
            repairs.append(
                _repair(packet, document.document_type, "content", "document content is empty")
            )
        if not document.evidence_ids:
            repairs.append(
                _repair(packet, document.document_type, "fact", "document has no evidence references")
            )
        unknown = sorted(set(document.evidence_ids) - evidence_ids)
        if unknown:
            repairs.append(
                _repair(
                    packet,
                    document.document_type,
                    "fact",
                    f"unknown evidence references: {', '.join(unknown)}",
                )
            )
        lowered = document.content.casefold()
        markers = tuple(marker for marker in PLACEHOLDER_MARKERS if marker in lowered)
        if markers:
            repairs.append(
                _repair(
                    packet,
                    document.document_type,
                    "ats",
                    f"placeholder markers present: {', '.join(markers)}",
                )
            )
        if document.document_type == "ats_answers" and document.content.strip() == "No ATS questions supplied.":
            repairs.append(
                _repair(packet, document.document_type, "ats", "ATS answers are not supplied")
            )

    missing_types = sorted(required_document_types - seen_types)
    for document_type in missing_types:
        repairs.append(
            _repair(packet, document_type, "structure", "required document type is missing")
        )
    return DocumentGateReport(passed=not repairs, repairs=tuple(repairs))
