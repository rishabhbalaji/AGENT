"""Bounded, approval-preserving orchestration for model-assisted drafts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from .database import DatabaseError, migrate
from .document_gates import DocumentGateReport, run_document_gates
from .documents import TailoredDocuments
from .evidence import EvidenceChunk
from .model_drafting import ModelDraftingResult, draft_with_model
from .normalization import PostingRecord
from .ollama import OllamaClient


DEFAULT_DAILY_LIMIT = 15
TECHNICAL_TERMS = frozenset(
    {"python", "java", "typescript", "javascript", "golang", "rust", "sql", "kubernetes", "software"}
)


@dataclass(frozen=True)
class DraftingCandidate:
    """A deterministic suitable posting eligible for local drafting."""

    posting: PostingRecord
    fit_score: int


@dataclass(frozen=True)
class DraftingOutcome:
    """One candidate's draft result and deterministic gate report."""

    candidate: DraftingCandidate
    model: str
    result: ModelDraftingResult | None
    gates: DocumentGateReport | None
    error: str | None = None


@dataclass(frozen=True)
class DraftingBatchResult:
    """Summary of one bounded drafting pass."""

    selected: tuple[DraftingCandidate, ...]
    outcomes: tuple[DraftingOutcome, ...]

    @property
    def passed(self) -> tuple[DraftingOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if outcome.gates and outcome.gates.passed)


EvidenceProvider = Callable[[PostingRecord], tuple[EvidenceChunk, ...]]


def select_drafting_candidates(
    candidates: Sequence[DraftingCandidate],
    *,
    limit: int = DEFAULT_DAILY_LIMIT,
) -> tuple[DraftingCandidate, ...]:
    """Select the highest-scoring candidates with a stable tie-breaker."""
    if limit < 1:
        raise ValueError("limit must be positive")
    return tuple(
        sorted(candidates, key=lambda item: (-item.fit_score, item.posting.stable_id))[:limit]
    )


def workload_for(candidate: DraftingCandidate) -> str:
    """Route technical postings to the technical model workload."""
    text = " ".join(
        (
            candidate.posting.posting.title,
            candidate.posting.posting.description,
            *candidate.posting.posting.requirements,
        )
    ).casefold()
    return "technical" if any(term in text for term in TECHNICAL_TERMS) else "routine"


def run_drafting_batch(
    candidates: Sequence[DraftingCandidate],
    *,
    evidence_provider: EvidenceProvider,
    clients: Mapping[str, OllamaClient],
    limit: int = DEFAULT_DAILY_LIMIT,
    database_path: Path | None = None,
) -> DraftingBatchResult:
    """Draft only the bounded top set and persist passed/repair records locally."""
    if not clients:
        raise ValueError("at least one model client is required")
    selected = select_drafting_candidates(candidates, limit=limit)
    workloads = {workload_for(candidate) for candidate in selected}
    for workload in workloads:
        client = clients.get(workload) or clients.get("routine")
        if client is None:
            raise ValueError(f"no model configured for workload: {workload}")
        client.check_health()
    outcomes: list[DraftingOutcome] = []
    for candidate in selected:
        workload = workload_for(candidate)
        client = clients.get(workload) or clients.get("routine")
        if client is None:
            raise ValueError(f"no model configured for workload: {workload}")
        try:
            evidence = evidence_provider(candidate.posting)
            result = draft_with_model(candidate.posting, evidence, client)
            gates = run_document_gates(result.documents, evidence)
            outcome = DraftingOutcome(candidate, client.config.model, result, gates)
            if database_path is not None:
                persist_drafting_outcome(database_path, outcome, evidence)
        except ValueError as exc:
            outcome = DraftingOutcome(candidate, client.config.model, None, None, str(exc))
        outcomes.append(outcome)
    return DraftingBatchResult(selected=selected, outcomes=tuple(outcomes))


def persist_drafting_outcome(
    database_path: Path,
    outcome: DraftingOutcome,
    evidence: tuple[EvidenceChunk, ...],
) -> None:
    """Persist local drafts and repair items without changing approval state."""
    if outcome.result is None or outcome.gates is None:
        return
    migrate(database_path)
    packet: TailoredDocuments = outcome.result.documents
    created_at = outcome.result.provenance.created_at.astimezone(timezone.utc).isoformat()
    evidence_ids = {chunk.chunk_id for chunk in evidence}
    try:
        with sqlite3.connect(database_path) as connection:
            for document in packet.documents:
                connection.execute(
                    """
                    INSERT INTO drafts(
                        job_id, document_type, title, content, evidence_ids_json,
                        model, model_version, gate_passed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        packet.posting_id,
                        document.document_type,
                        document.title,
                        document.content,
                        json.dumps(sorted(set(document.evidence_ids) & evidence_ids)),
                        outcome.result.provenance.model,
                        outcome.result.provenance.model_version,
                        int(outcome.gates.passed),
                        created_at,
                    ),
                )
            for repair in outcome.gates.repairs:
                connection.execute(
                    """
                    INSERT INTO repair_queue(job_id, document_type, gate, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (repair.posting_id, repair.document_type, repair.gate, repair.reason, created_at),
                )
            connection.execute(
                """
                INSERT INTO events(event_type, entity_type, entity_id, payload_json, created_at)
                VALUES ('drafting_completed', 'job', ?, ?, datetime('now'))
                """,
                (
                    packet.posting_id,
                    json.dumps(
                        {
                            "gate_passed": outcome.gates.passed,
                            "model": outcome.result.provenance.model,
                            "model_version": outcome.result.provenance.model_version,
                        },
                        sort_keys=True,
                    ),
                ),
            )
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot persist drafting outcome: {exc}") from exc
