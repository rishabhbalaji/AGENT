"""Load and validate fictional, offline fixtures used by early stages."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import DatabaseError, migrate


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


def seed_fixture_database(database_path: Path, fixtures_dir: Path) -> int:
    """Seed a local database with validated fictional postings for manual review."""
    fixture_set = load_fixture_set(fixtures_dir)
    migrate(database_path)
    decisions = {
        decision["job_id"]: decision for decision in fixture_set["route_decisions"]
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    inserted = 0
    try:
        with sqlite3.connect(database_path) as connection:
            for posting in fixture_set["postings"]:
                job_id = posting["job_id"]
                decision = decisions[job_id]
                status = "parked" if decision["route"] == "park" else "drafted"
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO jobs(
                        id, title, company, location, source, source_url,
                        description, first_seen_at, last_seen_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        posting["title"],
                        posting["company"],
                        posting.get("location"),
                        posting["source"],
                        posting["source_url"],
                        posting["description"],
                        timestamp,
                        timestamp,
                        status,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO applications(
                            id, job_id, route, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"{job_id}-fixture-application",
                            job_id,
                            decision["route"],
                            "parked" if status == "parked" else "drafted",
                            timestamp,
                            timestamp,
                        ),
                    )
            connection.execute(
                """
                INSERT INTO events(event_type, entity_type, entity_id, payload_json, created_at)
                VALUES ('fixture_seeded', 'database', ?, ?, datetime('now'))
                """,
                (str(database_path), json.dumps({"inserted": inserted}, sort_keys=True)),
            )
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot seed fixture database {database_path}: {exc}") from exc
    return inserted
