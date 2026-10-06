"""Deterministic discovery orchestration for public job sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Iterable
import json
import sqlite3
from pathlib import Path

from .ats import SourceAdapter
from .config import Configuration
from .database import DatabaseError, migrate
from .matching import MatchDecision, match_enabled_profiles
from .normalization import normalize_posting


@dataclass(frozen=True)
class DiscoveredJob:
    """One normalized posting and its best deterministic profile decision."""

    stable_id: str
    title: str
    company: str
    location: str | None
    source_url: str
    description: str
    status: str
    fit_score: int
    decision: MatchDecision


@dataclass(frozen=True)
class DiscoveryReport:
    """A source fetch result summarized for CLI and tests."""

    source: str
    health_status: str
    records_seen: int
    jobs: tuple[DiscoveredJob, ...]
    persisted: bool


@dataclass(frozen=True)
class MultiDiscoveryReport:
    """Combined result for one sequential pass across public sources."""

    reports: tuple[DiscoveryReport, ...]
    jobs: tuple[DiscoveredJob, ...]
    persisted: bool


def _best_decision(decisions: tuple[MatchDecision, ...]) -> MatchDecision:
    if not decisions:
        raise ValueError("at least one enabled profile is required")
    return max(
        decisions,
        key=lambda decision: (decision.matched, not decision.excluded, decision.score),
    )


def _status(decision: MatchDecision) -> str:
    if decision.excluded:
        return "parked"
    if decision.matched:
        return "drafted"
    return "discovered"


def _persist(
    database_path: Path,
    source: str,
    jobs: tuple[DiscoveredJob, ...],
    *,
    fetched_at: datetime,
) -> None:
    migrate(database_path)
    timestamp = fetched_at.isoformat()
    try:
        with sqlite3.connect(database_path) as connection:
            for job in jobs:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        id, title, company, location, source, source_url,
                        description, first_seen_at, last_seen_at, status, fit_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        source_url = excluded.source_url,
                        description = excluded.description,
                        last_seen_at = excluded.last_seen_at,
                        fit_score = excluded.fit_score
                    """,
                    (
                        job.stable_id,
                        job.title,
                        job.company,
                        job.location,
                        source,
                        job.source_url,
                        job.description,
                        timestamp,
                        timestamp,
                        job.status,
                        job.fit_score,
                    ),
                )
                if job.status in {"drafted", "parked"}:
                    route = "draft_for_approval" if job.status == "drafted" else "park"
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO applications(
                            id, job_id, route, status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"{job.stable_id}-discovery",
                            job.stable_id,
                            route,
                            "drafted" if job.status == "drafted" else "parked",
                            timestamp,
                            timestamp,
                        ),
                    )
            connection.execute(
                """
                INSERT INTO events(event_type, entity_type, entity_id, payload_json, created_at)
                VALUES ('discovery_completed', 'source', ?, ?, datetime('now'))
                """,
                (
                    source,
                    json.dumps(
                        {"records_seen": len(jobs), "persisted": True},
                        sort_keys=True,
                    ),
                ),
            )
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot persist discovery results: {exc}") from exc


def discover(
    adapter: SourceAdapter,
    configuration: Configuration,
    *,
    database_path: Path | None = None,
    dry_run: bool = True,
) -> DiscoveryReport:
    """Fetch, normalize, match, and optionally persist one public source."""
    result = adapter.fetch()
    jobs: list[DiscoveredJob] = []
    for posting in result.postings:
        record = normalize_posting(posting, fetched_at=result.fetched_at)
        decisions = match_enabled_profiles(
            posting,
            configuration.profiles.get("profiles", {}),
            clearance_exclusions=tuple(
                configuration.policy["clearance"]["exclude_required_or_requested"]
            ),
            company_exclusions=tuple(configuration.policy["company_exclusions"]),
        )
        decision = _best_decision(decisions)
        jobs.append(
            DiscoveredJob(
                stable_id=record.stable_id,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                source_url=record.source_url,
                description=posting.description,
                status=_status(decision),
                fit_score=decision.score,
                decision=decision,
            )
        )
    discovered = tuple(jobs)
    if not dry_run:
        if database_path is None:
            raise ValueError("database_path is required when dry_run is false")
        _persist(database_path, adapter.name, discovered, fetched_at=result.fetched_at)
    return DiscoveryReport(
        source=adapter.name,
        health_status=result.health.status.value,
        records_seen=result.health.records_seen,
        jobs=discovered,
        persisted=not dry_run,
    )


def discover_sources(
    adapters: Iterable[SourceAdapter],
    configuration: Configuration,
    *,
    database_path: Path | None = None,
    dry_run: bool = True,
) -> MultiDiscoveryReport:
    """Run every adapter sequentially and deduplicate stable postings.

    A source's failure is represented by its own unavailable health report;
    it does not prevent other public sources from being evaluated.
    """
    reports: list[DiscoveryReport] = []
    by_id: dict[str, DiscoveredJob] = {}
    for adapter in adapters:
        report = discover(
            adapter,
            configuration,
            database_path=None if dry_run else database_path,
            dry_run=dry_run,
        )
        reports.append(report)
        for job in report.jobs:
            by_id.setdefault(job.stable_id, job)
    jobs = tuple(by_id.values())
    return MultiDiscoveryReport(
        reports=tuple(reports),
        jobs=jobs,
        persisted=not dry_run,
    )
