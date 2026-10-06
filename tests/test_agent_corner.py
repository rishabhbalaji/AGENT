import tempfile
import unittest
from pathlib import Path

from job_engine.agent_corner import (
    AgentCornerIsolationError,
    AgentCornerPaths,
    prepare_paths,
    write_artifact,
)


class AgentCornerTests(unittest.TestCase):
    def test_prepares_separate_data_credentials_browser_and_jobs_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = prepare_paths(
                AgentCornerPaths.from_root(base / "agent-corner"),
                production_root=base / "runtime",
            )
            self.assertTrue(paths.data.is_dir())
            self.assertTrue(paths.credentials.is_dir())
            self.assertTrue(paths.browser.is_dir())
            self.assertTrue(paths.jobs.is_dir())

    def test_rejects_agent_corner_inside_production_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaises(AgentCornerIsolationError):
                prepare_paths(
                    AgentCornerPaths.from_root(base / "runtime" / "agent-corner"),
                    production_root=base / "runtime",
                )

    def test_artifact_cannot_escape_isolated_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = prepare_paths(
                AgentCornerPaths.from_root(base / "agent-corner"),
                production_root=base / "runtime",
            )
            with self.assertRaises(AgentCornerIsolationError):
                write_artifact(paths, name="../production.txt", content="blocked")
