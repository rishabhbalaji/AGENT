"""Strict validation and provenance records for model-generated output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any


class ModelOutputValidationError(ValueError):
    """Raised when model output or its provenance is invalid."""


@dataclass(frozen=True)
class ModelProvenance:
    """The reproducibility metadata required for one model invocation."""

    prompt: str
    model: str
    model_version: str
    revision: str
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("prompt", "model", "model_version", "revision"):
            if not getattr(self, field_name).strip():
                raise ModelOutputValidationError(f"{field_name} must be non-empty")
        if self.created_at.tzinfo is None:
            raise ModelOutputValidationError("created_at must be timezone-aware")


@dataclass(frozen=True)
class ValidatedModelOutput:
    """A strict payload paired with its schema and invocation provenance."""

    schema_name: str
    schema_version: int
    payload: dict[str, Any]
    provenance: ModelProvenance


def _validate_schema_identity(schema_name: str, schema_version: int) -> None:
    if not schema_name.strip():
        raise ModelOutputValidationError("schema_name must be non-empty")
    if schema_version < 1:
        raise ModelOutputValidationError("schema_version must be positive")


def validate_model_output(
    payload: object,
    *,
    schema_name: str,
    schema_version: int,
    required_fields: tuple[str, ...],
    allowed_fields: tuple[str, ...],
    provenance: ModelProvenance,
) -> ValidatedModelOutput:
    """Validate an object against an explicit, closed field schema."""
    _validate_schema_identity(schema_name, schema_version)
    if not isinstance(payload, dict):
        raise ModelOutputValidationError("model output must be a JSON object")
    allowed = set(allowed_fields)
    required = set(required_fields)
    if not required <= allowed:
        raise ModelOutputValidationError("required fields must be allowed fields")
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ModelOutputValidationError(
            f"model output contains unknown fields: {', '.join(unknown)}"
        )
    missing = sorted(required - set(payload))
    if missing:
        raise ModelOutputValidationError(
            f"model output is missing required fields: {', '.join(missing)}"
        )
    if any(not isinstance(field, str) or not field.strip() for field in payload):
        raise ModelOutputValidationError("model output field names must be non-empty strings")
    return ValidatedModelOutput(
        schema_name=schema_name.strip(),
        schema_version=schema_version,
        payload=dict(payload),
        provenance=provenance,
    )


def parse_model_output(
    raw_json: str,
    *,
    schema_name: str,
    schema_version: int,
    required_fields: tuple[str, ...],
    allowed_fields: tuple[str, ...],
    provenance: ModelProvenance,
) -> ValidatedModelOutput:
    """Parse JSON and apply the same closed-schema validation."""
    try:
        payload = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ModelOutputValidationError("model output is not valid JSON") from exc
    return validate_model_output(
        payload,
        schema_name=schema_name,
        schema_version=schema_version,
        required_fields=required_fields,
        allowed_fields=allowed_fields,
        provenance=provenance,
    )
