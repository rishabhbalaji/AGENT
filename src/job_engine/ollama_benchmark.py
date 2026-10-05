"""Fixture-only evaluation of configured Ollama models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from time import monotonic
from typing import Any

from .model_output import ModelOutputValidationError, ModelProvenance, parse_model_output
from .ollama import OllamaClient, OllamaConfig, OllamaError


BENCHMARK_SCHEMA = "ollama_benchmark_triage"
BENCHMARK_SCHEMA_VERSION = 1
BENCHMARK_FIELDS = (
    "role",
    "seniority",
    "sponsorship",
    "clearance_required",
    "route",
)

FIXTURE_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "suitable-python-role",
        "title": "Junior Python Automation Developer",
        "company": "Northstar Systems",
        "description": "Build tested Python automation and maintain internal documentation.",
        "requirements": ["Python", "technical documentation"],
        "clearance_requirements": [],
    },
    {
        "case_id": "sc-clearance-exclusion",
        "title": "Python Developer",
        "company": "Civic Example Ltd",
        "description": "Maintain Python services for a public-sector programme.",
        "requirements": ["Python"],
        "clearance_requirements": ["SC Clearance"],
    },
)


@dataclass(frozen=True)
class BenchmarkResult:
    """One model/case result suitable for local comparison."""

    model: str
    digest: str | None
    case_id: str
    elapsed_ms: float | None
    status: str
    schema_valid: bool
    route: str | None
    error: str | None


def _prompt(case: dict[str, Any]) -> str:
    return (
        "You are evaluating a fictional job posting for a local benchmark. "
        "Return only a JSON object with exactly these string/boolean fields: "
        "role, seniority, sponsorship, clearance_required, route. "
        "The route must be one of park, review, or draft_for_approval. "
        "Required or requested SC Clearance must always produce route park. "
        "Do not invent facts.\n\n"
        f"{json.dumps(case, sort_keys=True)}"
    )


def benchmark_models(
    endpoint: str,
    models: tuple[str, ...],
    *,
    timeout_seconds: float = 60.0,
) -> tuple[BenchmarkResult, ...]:
    """Run the fixed cases against each model and fail closed per result."""
    if not models:
        raise ValueError("at least one model is required")
    results: list[BenchmarkResult] = []
    for model_name in models:
        client = OllamaClient(OllamaConfig(endpoint, model_name, timeout_seconds))
        digest: str | None = None
        try:
            health = client.check_health()
            digest = health.model.digest
        except (OllamaError, ValueError) as exc:
            for case in FIXTURE_CASES:
                results.append(
                    BenchmarkResult(
                        model=model_name,
                        digest=None,
                        case_id=case["case_id"],
                        elapsed_ms=None,
                        status="failed",
                        schema_valid=False,
                        route=None,
                        error=str(exc),
                    )
                )
            continue
        for case in FIXTURE_CASES:
            started = monotonic()
            try:
                raw = client.generate_json(_prompt(case))
                provenance = ModelProvenance(
                    prompt=_prompt(case),
                    model=model_name,
                    model_version=digest,
                    revision=BENCHMARK_SCHEMA,
                    created_at=datetime.now(timezone.utc),
                )
                output = parse_model_output(
                    raw,
                    schema_name=BENCHMARK_SCHEMA,
                    schema_version=BENCHMARK_SCHEMA_VERSION,
                    required_fields=BENCHMARK_FIELDS,
                    allowed_fields=BENCHMARK_FIELDS,
                    provenance=provenance,
                )
                route = output.payload["route"]
                if case["case_id"] == "sc-clearance-exclusion" and route != "park":
                    raise ModelOutputValidationError(
                        "SC-clearance fixture must produce route park"
                    )
                results.append(
                    BenchmarkResult(
                        model=model_name,
                        digest=digest,
                        case_id=case["case_id"],
                        elapsed_ms=round((monotonic() - started) * 1000, 2),
                        status="passed",
                        schema_valid=True,
                        route=route if isinstance(route, str) else None,
                        error=None,
                    )
                )
            except (OllamaError, ModelOutputValidationError, ValueError) as exc:
                results.append(
                    BenchmarkResult(
                        model=model_name,
                        digest=digest,
                        case_id=case["case_id"],
                        elapsed_ms=round((monotonic() - started) * 1000, 2),
                        status="failed",
                        schema_valid=False,
                        route=None,
                        error=str(exc),
                    )
                )
    return tuple(results)


def results_as_json(results: tuple[BenchmarkResult, ...]) -> str:
    """Serialize benchmark results without including prompts or job secrets."""
    return json.dumps([asdict(result) for result in results], indent=2, sort_keys=True)
