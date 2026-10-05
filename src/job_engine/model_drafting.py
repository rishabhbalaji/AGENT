"""Fixture-only, evidence-constrained model drafting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from .claims import Claim, ValidatedClaim, validate_claims
from .documents import TailoredDocuments, generate_tailored_documents
from .evidence import EvidenceChunk
from .model_output import ModelOutputValidationError, ModelProvenance, parse_model_output
from .ollama import OllamaClient
from .normalization import PostingRecord


MODEL_DRAFTING_SCHEMA = "model_drafting"
MODEL_DRAFTING_FIELDS = ("claims", "ats_answers", "linkedin_message")


@dataclass(frozen=True)
class ModelDraftingResult:
    """Evidence-validated documents and the model provenance that produced them."""

    documents: TailoredDocuments
    provenance: ModelProvenance


def _prompt(posting: PostingRecord, evidence: tuple[EvidenceChunk, ...]) -> str:
    return (
        "Prepare an evidence-constrained fictional job application draft. "
        "Return only JSON with exactly these fields: claims, ats_answers, "
        "linkedin_message. claims must be a list of objects with text and "
        "evidence_ids; every evidence ID must come from the supplied evidence. "
        "ats_answers must be a list of objects with question and answer. "
        "Do not invent qualifications or evidence.\n\n"
        + json.dumps(
            {
                "posting": {
                    "title": posting.posting.title,
                    "company": posting.posting.company,
                    "description": posting.posting.description,
                    "requirements": posting.posting.requirements,
                },
                "evidence": [
                    {"chunk_id": chunk.chunk_id, "content": chunk.content}
                    for chunk in evidence
                ],
            },
            sort_keys=True,
        )
    )


def draft_with_model(
    posting: PostingRecord,
    evidence: tuple[EvidenceChunk, ...],
    client: OllamaClient,
) -> ModelDraftingResult:
    """Generate documents only after model claims pass local evidence validation."""
    if not evidence:
        raise ValueError("evidence must not be empty")
    prompt = _prompt(posting, evidence)
    health = client.check_health()
    raw = client.generate_json(prompt)
    provenance = ModelProvenance(
        prompt=prompt,
        model=client.config.model,
        model_version=health.model.digest,
        revision=MODEL_DRAFTING_SCHEMA,
        created_at=datetime.now(timezone.utc),
    )
    output = parse_model_output(
        raw,
        schema_name=MODEL_DRAFTING_SCHEMA,
        schema_version=1,
        required_fields=MODEL_DRAFTING_FIELDS,
        allowed_fields=MODEL_DRAFTING_FIELDS,
        provenance=provenance,
    )
    claims_payload = output.payload["claims"]
    answers_payload = output.payload["ats_answers"]
    linkedin_message = output.payload["linkedin_message"]
    if not isinstance(claims_payload, list) or not claims_payload:
        raise ModelOutputValidationError("claims must be a non-empty list")
    claims: list[Claim] = []
    for item in claims_payload:
        if not isinstance(item, dict):
            raise ModelOutputValidationError("each claim must be an object")
        text = item.get("text")
        evidence_ids = item.get("evidence_ids")
        if not isinstance(text, str) or not isinstance(evidence_ids, list):
            raise ModelOutputValidationError("claims require text and evidence_ids")
        if not all(isinstance(value, str) for value in evidence_ids):
            raise ModelOutputValidationError("claim evidence_ids must be strings")
        claims.append(Claim(text=text, evidence_ids=tuple(evidence_ids)))
    validated: tuple[ValidatedClaim, ...] = validate_claims(claims, evidence)
    if not isinstance(answers_payload, list):
        raise ModelOutputValidationError("ats_answers must be a list")
    answers: list[tuple[str, str]] = []
    for item in answers_payload:
        if not isinstance(item, dict) or not isinstance(item.get("question"), str) or not isinstance(item.get("answer"), str):
            raise ModelOutputValidationError("ATS answers require question and answer")
        answers.append((item["question"], item["answer"]))
    if not isinstance(linkedin_message, str):
        raise ModelOutputValidationError("linkedin_message must be a string")
    documents = generate_tailored_documents(
        posting,
        validated,
        ats_answers=tuple(answers),
        linkedin_message=linkedin_message,
        created_at=provenance.created_at,
    )
    return ModelDraftingResult(documents=documents, provenance=provenance)
