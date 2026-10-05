import tempfile
from pathlib import Path
from unittest import TestCase

from job_engine.worker import clear_pause, pause_status, run_bounded_worker, set_pause


class WorkerTests(TestCase):
    def test_pause_can_be_set_cleared_and_read(self):
        with tempfile.TemporaryDirectory() as directory:
            pause = Path(directory) / "controls" / "PAUSED"
            self.assertFalse(pause_status(pause))
            set_pause(pause)
            self.assertTrue(pause_status(pause))
            clear_pause(pause)
            self.assertFalse(pause_status(pause))

    def test_pause_prevents_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pause = root / "paused"
            pause.touch()
            called = []
            result = run_bounded_worker(
                lambda: called.append(True),
                lock_path=root / "worker.lock",
                pause_path=pause,
            )
            self.assertEqual(result.status, "paused")
            self.assertEqual(called, [])

    def test_task_runs_and_returns_value(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_bounded_worker(
                lambda: {"sources": 2},
                lock_path=Path(directory) / "worker.lock",
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.value, {"sources": 2})
