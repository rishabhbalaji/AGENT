"""Fixture evaluation of model-generated documents against local gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .document_gates import DocumentGateReport, run_document_gates
from .evidence import EvidenceChunk
from .model_drafting import draft_with_model
from .normalization import PostingRecord
from .ollama import OllamaClient, OllamaError


@dataclass(frozen=True)
class ModelGateEvaluation:
    """Serializable result for one model draft evaluation."""

    model: str
    digest: str | None
    drafting_status: str
    gates_passed: bool
    repair_count: int
    error: str | None


def evaluate_model_draft(
    posting: PostingRecord,
    evidence: tuple[EvidenceChunk, ...],
    client: OllamaClient,
) -> ModelGateEvaluation:
    """Run model drafting and deterministic gates without persisting anything."""
    try:
        result = draft_with_model(posting, evidence, client)
        report: DocumentGateReport = run_document_gates(result.documents, evidence)
        return ModelGateEvaluation(
            model=result.provenance.model,
            digest=result.provenance.model_version,
            drafting_status="passed",
            gates_passed=report.passed,
            repair_count=len(report.repairs),
            error=None if report.passed else "document gates failed",
        )
    except (OllamaError, ValueError) as exc:
        return ModelGateEvaluation(
            model=client.config.model,
            digest=None,
            drafting_status="failed",
            gates_passed=False,
            repair_count=0,
            error=str(exc),
        )


def evaluation_as_json(result: ModelGateEvaluation) -> str:
    """Serialize one local evaluation result."""
    return json.dumps(asdict(result), indent=2, sort_keys=True)
