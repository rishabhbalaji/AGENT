"""Load and validate fictional, offline fixtures used by early stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    """Raised when an offline fixture set is unsafe or inconsistent."""


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"{path.name}: cannot load JSON fixture: {exc}") from exc


def load_fixture_set(fixtures_dir: Path) -> dict[str, Any]:
    """Load the persona, postings, and route decisions fixture set."""
    fixtures_dir = fixtures_dir.expanduser()
    persona = _load_json(fixtures_dir / "persona.json")
    postings = _load_json(fixtures_dir / "postings.json")
    decisions = _load_json(fixtures_dir / "route_decisions.json")

    if not isinstance(persona, dict) or persona.get("version") != 1:
        raise FixtureError("persona.json: version 1 mapping is required")
    if not isinstance(postings, list) or not postings:
        raise FixtureError("postings.json: a non-empty list is required")
    if not isinstance(decisions, list) or not decisions:
        raise FixtureError("route_decisions.json: a non-empty list is required")

    job_ids: set[str] = set()
    for posting in postings:
        if not isinstance(posting, dict) or posting.get("version") != 1:
            raise FixtureError("postings.json: every posting must use version 1")
        job_id = posting.get("job_id")
        if not isinstance(job_id, str) or not job_id or job_id in job_ids:
            raise FixtureError("postings.json: job IDs must be unique non-empty strings")
        if not str(posting.get("source_url", "")).startswith("https://example.invalid/"):
            raise FixtureError("postings.json: fixture URLs must use example.invalid")
        job_ids.add(job_id)

    decision_ids: set[str] = set()
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("version") != 1:
            raise FixtureError("route_decisions.json: every decision must use version 1")
        job_id = decision.get("job_id")
        if job_id not in job_ids or job_id in decision_ids:
            raise FixtureError("route_decisions.json: decisions must map one-to-one to postings")
        if decision.get("route") == "submit":
            raise FixtureError("route_decisions.json: fixtures must not submit applications")
        decision_ids.add(job_id)

    if decision_ids != job_ids:
        raise FixtureError("route_decisions.json: every posting needs one route decision")
    return {"persona": persona, "postings": postings, "route_decisions": decisions}
