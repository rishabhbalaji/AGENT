import tempfile
import unittest
from pathlib import Path

from job_engine.config import ConfigurationError, load_config


ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "config" / "examples"


class ConfigurationTests(unittest.TestCase):
    def test_loads_example_configuration(self):
        configuration = load_config(EXAMPLES)
        self.assertIn("full_time", configuration.profiles["profiles"])
        self.assertEqual(configuration.policy["discovery"]["suitable_jobs_target_per_day"], 15)
        self.assertFalse(configuration.policy["n8n"]["enabled"])

    def test_n8n_cannot_own_business_logic_or_state(self):
        with tempfile.TemporaryDirectory() as directory:
            for source in EXAMPLES.glob("*.yaml"):
                (Path(directory) / source.name).write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
            policy = Path(directory) / "policy.yaml"
            content = policy.read_text(encoding="utf-8").replace(
                "owns_business_logic: false", "owns_business_logic: true"
            )
            policy.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "owns_business_logic"):
                load_config(Path(directory))

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigurationError, "profiles.yaml"):
                load_config(Path(directory))

    def test_invalid_yaml_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.yaml"
            path.write_text("version: [broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "invalid YAML"):
                from job_engine.config import _load_document

                _load_document(path)

    def test_wrong_version_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.yaml"
            path.write_text("version: 2\nprofiles: {}\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "version must be 1"):
                from job_engine.config import _load_document

                _load_document(path)

    def test_non_github_repository_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            for source in EXAMPLES.glob("*.yaml"):
                (Path(directory) / source.name).write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
            (Path(directory) / "repositories.yaml").write_text(
                "version: 1\nrepositories:\n  - https://example.com/repo\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "GitHub URLs"):
                load_config(Path(directory))
