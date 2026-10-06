import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from job_engine.ats import NormalizedPosting
from job_engine.database import migrate
from job_engine.drafting_worker import (
    DraftingCandidate,
    run_drafting_batch,
    select_drafting_candidates,
    workload_for,
)
from job_engine.evidence import EvidenceChunk
from job_engine.normalization import normalize_posting


def _candidate(job_id: str, score: int, title: str = "Operations Coordinator") -> DraftingCandidate:
    posting = normalize_posting(
        NormalizedPosting(
            source_name="fixture",
            source_job_id=job_id,
            title=title,
            company="Example Co",
            location="Manchester",
            source_url=f"https://example.invalid/jobs/{job_id}",
            description="Coordinate delivery work.",
            requirements=("Communication",),
            clearance_requirements=(),
        ),
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return DraftingCandidate(posting, score)


class DraftingWorkerTests(unittest.TestCase):
    def test_selection_is_bounded_and_sorted_by_score(self):
        candidates = [_candidate("b", 80), _candidate("a", 90), _candidate("c", 90)]
        selected = select_drafting_candidates(candidates, limit=2)
        self.assertEqual([item.fit_score for item in selected], [90, 90])
        self.assertEqual(selected[0].posting.stable_id, min(
            candidates[1].posting.stable_id,
            candidates[2].posting.stable_id,
        ))

    def test_technical_workload_is_routed_separately(self):
        self.assertEqual(workload_for(_candidate("tech", 90, "Python Developer")), "technical")
        self.assertEqual(workload_for(_candidate("ops", 90)), "routine")

    def test_passed_drafts_are_persisted_locally(self):
        candidate = _candidate("draft", 90, "Python Developer")
        evidence = (EvidenceChunk("e1", "resume", "resume.txt", 0, "Built Python automation.", "hash"),)
        client = Mock()
        client.config.model = "technical-model"
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.return_value = json.dumps(
            {
                "claims": [{"text": "Built Python automation.", "evidence_ids": ["e1"]}],
                "ats_answers": [{"question": "Why Python?", "answer": "I build automation."}],
                "linkedin_message": "Hello, I am interested in this role.",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            result = run_drafting_batch(
                [candidate],
                evidence_provider=lambda _: evidence,
                clients={"technical": client},
                database_path=database,
            )
            self.assertEqual(len(result.passed), 1)
            migrate(database)
            import sqlite3

            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 4)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM repair_queue").fetchone()[0], 0)

    def test_ollama_failure_stops_before_processing_candidates(self):
        client = Mock()
        client.config.model = "routine-model"
        client.check_health.side_effect = RuntimeError("offline")
        with self.assertRaisesRegex(RuntimeError, "offline"):
            run_drafting_batch(
                [_candidate("one", 90)],
                evidence_provider=lambda _: (),
                clients={"routine": client},
            )
