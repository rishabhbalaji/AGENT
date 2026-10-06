import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from job_engine.config import load_config
from job_engine.database import migrate
from job_engine.deep_review import (
    actionable_queue_depth,
    deep_review_is_allowed,
    run_deep_review_worker,
)


CONFIG = load_config(Path(__file__).parents[1] / "config" / "examples")


class DeepReviewTests(unittest.TestCase):
    def test_window_allows_only_midnight_to_two_uk_time(self):
        self.assertTrue(
            deep_review_is_allowed(
                CONFIG,
                actionable_depth=0,
                at=datetime(2026, 1, 5, 1, 0),
            )
        )
        self.assertFalse(
            deep_review_is_allowed(
                CONFIG,
                actionable_depth=0,
                at=datetime(2026, 1, 5, 2, 0),
            )
        )

    def test_queue_gate_blocks_when_actionable_work_exists(self):
        self.assertFalse(
            deep_review_is_allowed(
                CONFIG,
                actionable_depth=1,
                at=datetime(2026, 1, 5, 1, 0),
            )
        )

    def test_worker_does_not_call_model_or_task_when_not_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            migrate(database)
            task = Mock()
            result = run_deep_review_worker(
                task,
                CONFIG,
                database_path=database,
                lock_path=Path(directory) / "worker.lock",
                at=datetime(2026, 1, 5, 3, 0),
            )
        self.assertEqual(result.status, "not_eligible")
        task.assert_not_called()

    def test_worker_checks_deep_model_before_task(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            migrate(database)
            client = Mock()
            with patch("job_engine.deep_review.OllamaClient", return_value=client):
                task = Mock(return_value="reviewed")
                result = run_deep_review_worker(
                    task,
                    CONFIG,
                    database_path=database,
                    lock_path=Path(directory) / "worker.lock",
                    at=datetime(2026, 1, 5, 1, 0),
                )
        self.assertEqual(result.status, "completed")
        task.assert_called_once_with()
        client.check_health.assert_called_once_with()

