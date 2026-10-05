"""Local, evidence-backed application document drafts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .claims import ValidatedClaim
from .normalization import PostingRecord


class DocumentGenerationError(ValueError):
    """Raised when a document draft cannot be generated safely."""


@dataclass(frozen=True)
class DocumentDraft:
    """One locally generated text document with its supporting evidence IDs."""

    document_type: str
    title: str
    content: str
    evidence_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class TailoredDocuments:
    """The review packet generated for one posting."""

    posting_id: str
    documents: tuple[DocumentDraft, ...]


def _claim_lines(claims: tuple[ValidatedClaim, ...]) -> tuple[str, ...]:
    return tuple(
        f"- {claim.text} [evidence: {', '.join(chunk.chunk_id for chunk in claim.evidence)}]"
        for claim in claims
    )


def _claim_ids(claims: tuple[ValidatedClaim, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(chunk.chunk_id for claim in claims for chunk in claim.evidence)
    )


def generate_tailored_documents(
    posting: PostingRecord,
    claims: tuple[ValidatedClaim, ...],
    *,
    ats_answers: tuple[tuple[str, str], ...] = (),
    linkedin_message: str | None = None,
    created_at: datetime | None = None,
) -> TailoredDocuments:
    """Create local resume, cover-letter, ATS, and LinkedIn text drafts.

    Claims must already have passed ``validate_claims``. No network calls,
    credentials, or application submissions occur.
    """
    if not claims:
        raise DocumentGenerationError("at least one validated claim is required")
    if any(not question.strip() or not answer.strip() for question, answer in ats_answers):
        raise DocumentGenerationError("ATS questions and answers must be non-empty")
    if linkedin_message is not None and not linkedin_message.strip():
        raise DocumentGenerationError("linkedin_message must be non-empty when provided")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise DocumentGenerationError("created_at must be timezone-aware")

    claim_lines = _claim_lines(claims)
    evidence_ids = _claim_ids(claims)
    title = posting.posting.title.strip()
    company = posting.posting.company.strip()
    documents = (
        DocumentDraft(
            "resume",
            f"Tailored resume — {title}",
            "\n".join((f"# {title}", f"Target company: {company}", "", *claim_lines)),
            evidence_ids,
            timestamp,
        ),
        DocumentDraft(
            "cover_letter",
            f"Cover letter — {title}",
            "\n".join(
                (
                    f"# Cover letter: {title}",
                    "",
                    f"Dear {company} hiring team,",
                    "",
                    "I am interested in this role because my relevant experience includes:",
                    *claim_lines,
                    "",
                    "Kind regards,",
                )
            ),
            evidence_ids,
            timestamp,
        ),
        DocumentDraft(
            "ats_answers",
            f"ATS answers — {title}",
            "\n".join(
                f"## {question}\n{answer}" for question, answer in ats_answers
            )
            or "No ATS questions supplied.",
            evidence_ids,
            timestamp,
        ),
        DocumentDraft(
            "linkedin_message",
            f"LinkedIn message — {title}",
            linkedin_message or f"Hello, I am interested in the {title} role at {company}.",
            evidence_ids,
            timestamp,
        ),
    )
    return TailoredDocuments(posting.stable_id, documents)
