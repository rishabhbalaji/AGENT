import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from job_engine.ollama import OllamaError
from job_engine.worker import (
    check_ollama_available,
    clear_pause,
    pause_status,
    run_bounded_worker,
    run_discovery_worker,
    set_pause,
)


class WorkerTests(TestCase):
    def test_ollama_gate_requires_configured_model(self):
        configuration = type(
            "Configuration",
            (),
            {"policy": {"ollama": {"endpoint": "http://ollama", "model": "qwen3:14b-16k"}}},
        )()
        client = type("Client", (), {"check_health": lambda self: None})()
        with patch("job_engine.worker.OllamaClient", return_value=client) as constructor:
            check_ollama_available(configuration)
        constructor.assert_called_once()

    def test_ollama_gate_fails_closed_when_unavailable(self):
        configuration = type(
            "Configuration",
            (),
            {"policy": {"ollama": {"endpoint": "http://ollama", "model": "qwen3:14b-16k"}}},
        )()
        client = type(
            "Client",
            (),
            {"check_health": lambda self: (_ for _ in ()).throw(OllamaError("offline"))},
        )()
        with patch("job_engine.worker.OllamaClient", return_value=client):
            with self.assertRaisesRegex(OllamaError, "offline"):
                check_ollama_available(configuration)

    def test_discovery_worker_does_not_start_discovery_when_ollama_is_unavailable(self):
        configuration = type(
            "Configuration",
            (),
            {"policy": {"ollama": {"endpoint": "http://ollama", "model": "qwen3:14b-16k"}}},
        )()
        client = type(
            "Client",
            (),
            {"check_health": lambda self: (_ for _ in ()).throw(OllamaError("offline"))},
        )()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("job_engine.worker.OllamaClient", return_value=client):
                with patch("job_engine.discovery.discover_sources") as discovery:
                    with self.assertRaisesRegex(OllamaError, "offline"):
                        run_discovery_worker(
                            [],
                            configuration,
                            database_path=root / "engine.sqlite3",
                            lock_path=root / "engine.lock",
                            pause_path=root / "PAUSED",
                        )
            discovery.assert_not_called()
            self.assertFalse((root / "engine.sqlite3").exists())

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
