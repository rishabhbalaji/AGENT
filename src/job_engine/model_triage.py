"""Fixture-only model assistance layered on deterministic triage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from .model_output import (
    ModelOutputValidationError,
    ModelProvenance,
    parse_model_output,
)
from .ollama import OllamaClient
from .triage import TriageRecord


MODEL_TRIAGE_SCHEMA = "model_triage"
MODEL_TRIAGE_FIELDS = (
    "role",
    "seniority",
    "sponsorship",
    "clearance_required",
    "route",
)
ALLOWED_ROUTES = {"park", "review", "draft_for_approval"}


@dataclass(frozen=True)
class ModelTriageComparison:
    """Model observations alongside the deterministic source of truth."""

    deterministic_route: str
    model_route: str
    route_matches: bool
    model_payload: dict[str, Any]
    provenance: ModelProvenance


def _prompt(record: TriageRecord) -> str:
    return (
        "Analyze this fictional normalized job triage record. Return only a JSON "
        "object with exactly these fields: role, seniority, sponsorship, "
        "clearance_required, route. Route must be one of park, review, or "
        "draft_for_approval. Required or requested SC Clearance must use park. "
        "Do not invent facts. This output is advisory; deterministic policy "
        "remains authoritative.\n\n"
        + json.dumps(
            {
                "role": record.role,
                "location": record.location,
                "salary_text": record.salary_text,
                "sponsorship": record.sponsorship,
                "seniority": record.seniority,
                "work_mode": record.work_mode,
                "fit_score": record.fit_score,
                "route": record.route,
                "unknowns": record.unknowns,
            },
            sort_keys=True,
        )
    )


def triage_with_model(
    record: TriageRecord,
    client: OllamaClient,
) -> ModelTriageComparison:
    """Validate model observations without allowing them to change the route."""
    prompt = _prompt(record)
    health = client.check_health()
    raw = client.generate_json(prompt)
    provenance = ModelProvenance(
        prompt=prompt,
        model=client.config.model,
        model_version=health.model.digest,
        revision=MODEL_TRIAGE_SCHEMA,
        created_at=datetime.now(timezone.utc),
    )
    output = parse_model_output(
        raw,
        schema_name=MODEL_TRIAGE_SCHEMA,
        schema_version=1,
        required_fields=MODEL_TRIAGE_FIELDS,
        allowed_fields=MODEL_TRIAGE_FIELDS,
        provenance=provenance,
    )
    payload = output.payload
    if not isinstance(payload["role"], str) or not payload["role"].strip():
        raise ModelOutputValidationError("model role must be a non-empty string")
    for field in ("seniority", "sponsorship", "route"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ModelOutputValidationError(f"model {field} must be a non-empty string")
    if not isinstance(payload["clearance_required"], bool):
        raise ModelOutputValidationError("model clearance_required must be boolean")
    model_route = payload["route"]
    if model_route not in ALLOWED_ROUTES:
        raise ModelOutputValidationError(f"model route is unsupported: {model_route}")
    if "clearance" in " ".join(record.unknowns).casefold() and model_route != "park":
        raise ModelOutputValidationError("clearance fixture must produce route park")
    return ModelTriageComparison(
        deterministic_route=record.route,
        model_route=model_route,
        route_matches=record.route == model_route,
        model_payload=payload,
        provenance=provenance,
    )
