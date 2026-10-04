import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from job_engine.health import run_health_check
from scripts.storage_check import MountInfo


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = ROOT / "config" / "examples"


class HealthCheckTests(unittest.TestCase):
    def test_health_check_validates_and_records_event(self):
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            result = run_health_check(
                config_dir=EXAMPLE_CONFIG,
                data_root=data_root,
                at=None,
                storage_validator=lambda _: MountInfo(
                    "/dev/sda1", frozenset({"rw", "relatime"})
                ),
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["mount_source"], "/dev/sda1")
            self.assertGreater(result["event_id"], 0)
            self.assertTrue((data_root / "engine.sqlite3").is_file())

    def test_health_check_resolves_paused_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_health_check(
                config_dir=EXAMPLE_CONFIG,
                data_root=Path(directory),
                paused=True,
                storage_validator=lambda _: MountInfo(
                    "/dev/sda1", frozenset({"rw"})
                ),
            )

        self.assertEqual(result["mode"], "paused")
        self.assertEqual(result["allowed_actions"], [])

    def test_cli_reports_storage_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_root = Path(directory) / "missing"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "job_engine.cli",
                    "health",
                    "--config-dir",
                    str(EXAMPLE_CONFIG),
                    "--data-root",
                    str(missing_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("health check failed", result.stderr)

    def test_health_result_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_health_check(
                config_dir=EXAMPLE_CONFIG,
                data_root=Path(directory),
                storage_validator=lambda _: MountInfo(
                    "/dev/sda1", frozenset({"rw"})
                ),
            )
        self.assertEqual(json.loads(json.dumps(result))["status"], "ok")
