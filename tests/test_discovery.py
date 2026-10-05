import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from job_engine.ats import NormalizedPosting, SourceFetchResult, SourceHealth, SourceHealthStatus
from job_engine.config import Configuration
from job_engine.discovery import discover, discover_sources


class Adapter:
    name = "fixture-source"

    def fetch(self):
        posting = NormalizedPosting(
            source_name=self.name,
            source_job_id="job-1",
            title="Python Developer",
            company="Example Co",
            source_url="https://example.invalid/jobs/1",
            description="Build Python tools.",
            employment_type="full_time",
            remote_mode="hybrid",
            requirements=("Python",),
        )
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return SourceFetchResult(
            (posting,),
            SourceHealth(self.name, SourceHealthStatus.HEALTHY, now, records_seen=1),
            now,
        )


def configuration():
    return Configuration(
        profiles={
            "profiles": {
                "full_time": {
                    "enabled": True,
                    "employment_types": ["full_time"],
                    "keywords": {"include": [], "exclude": []},
                    "locations": {"include": []},
                    "remote": {"modes": ["hybrid"], "allowed_countries": [], "worldwide": True},
                    "salary": {"minimum_gbp": None},
                    "score_threshold": 30,
                }
            }
        },
        schedule={},
        sources={},
        repositories={},
        policy={
            "clearance": {"exclude_required_or_requested": ["SC"]},
            "company_exclusions": [],
        },
    )


class DiscoveryTests(TestCase):
    def test_multiple_sources_are_combined_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            report = discover_sources(
                (Adapter(), Adapter()),
                configuration(),
                database_path=Path(directory) / "engine.sqlite3",
            )
            self.assertEqual(len(report.reports), 2)
            self.assertEqual(len(report.jobs), 1)
            self.assertFalse(report.persisted)

    def test_dry_run_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.sqlite3"
            report = discover(Adapter(), configuration(), database_path=path)
            self.assertFalse(report.persisted)
            self.assertEqual(report.jobs[0].status, "drafted")
            self.assertFalse(path.exists())

    def test_persisted_discovery_creates_job_and_application(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.sqlite3"
            report = discover(Adapter(), configuration(), database_path=path, dry_run=False)
            self.assertTrue(report.persisted)
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
                self.assertEqual(
                    connection.execute("SELECT status FROM jobs").fetchone()[0],
                    "drafted",
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
                    1,
                )
