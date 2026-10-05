"""Offline ATS application-form fixtures and safety validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ATSFixtureError(ValueError):
    """Raised when an ATS fixture is malformed or unsafe."""


SUPPORTED_FIELD_TYPES = {"text", "textarea", "email", "select", "checkbox"}


@dataclass(frozen=True)
class ATSField:
    name: str
    label: str
    field_type: str
    required: bool
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ATSFormFixture:
    provider: str
    job_id: str
    application_url: str
    fields: tuple[ATSField, ...]
    supports_submission: bool = False

    def required_field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    def validate_answers(self, answers: dict[str, Any]) -> None:
        """Validate answers without sending or mutating anything externally."""
        known = {field.name: field for field in self.fields}
        unknown = set(answers) - set(known)
        if unknown:
            raise ATSFixtureError(f"unknown form fields: {', '.join(sorted(unknown))}")
        missing = [
            field.name
            for field in self.fields
            if field.required and not _has_answer(answers.get(field.name))
        ]
        if missing:
            raise ATSFixtureError(f"missing required fields: {', '.join(missing)}")
        for name, answer in answers.items():
            field = known[name]
            if field.field_type == "select" and answer not in field.options:
                raise ATSFixtureError(f"invalid option for {name}: {answer}")
            if field.field_type == "checkbox" and not isinstance(answer, bool):
                raise ATSFixtureError(f"checkbox field {name} must be boolean")


def _has_answer(value: Any) -> bool:
    return value is True or (isinstance(value, str) and bool(value.strip()))


def load_form_fixture(path: Path) -> ATSFormFixture:
    """Load and validate one offline ATS form fixture."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ATSFixtureError(f"{path}: cannot load fixture: {exc}") from exc
    if not isinstance(document, dict):
        raise ATSFixtureError("fixture root must be an object")
    provider = document.get("provider")
    job_id = document.get("job_id")
    application_url = document.get("application_url")
    fields = document.get("fields")
    if not all(isinstance(value, str) and value.strip() for value in (provider, job_id, application_url)):
        raise ATSFixtureError("provider, job_id, and application_url are required")
    if not application_url.startswith("https://example.invalid/"):
        raise ATSFixtureError("application_url must use example.invalid")
    if not isinstance(fields, list) or not fields:
        raise ATSFixtureError("fields must be a non-empty list")
    parsed: list[ATSField] = []
    names: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ATSFixtureError("every field must be an object")
        name, label, field_type = (field.get(key) for key in ("name", "label", "type"))
        if not all(isinstance(value, str) and value.strip() for value in (name, label, field_type)):
            raise ATSFixtureError("every field requires name, label, and type")
        if field_type not in SUPPORTED_FIELD_TYPES:
            raise ATSFixtureError(f"unsupported field type: {field_type}")
        if name in names:
            raise ATSFixtureError(f"duplicate field name: {name}")
        names.add(name)
        options = field.get("options", [])
        if field_type == "select" and (
            not isinstance(options, list) or not options or not all(isinstance(option, str) for option in options)
        ):
            raise ATSFixtureError(f"select field {name} requires options")
        parsed.append(
            ATSField(
                name=name,
                label=label,
                field_type=field_type,
                required=bool(field.get("required", False)),
                options=tuple(options),
            )
        )
    return ATSFormFixture(
        provider=provider,
        job_id=job_id,
        application_url=application_url,
        fields=tuple(parsed),
        supports_submission=bool(document.get("supports_submission", False)),
    )
