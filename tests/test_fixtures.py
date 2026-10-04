import tempfile
import unittest
from pathlib import Path

from job_engine.fixtures import FixtureError, load_fixture_set


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class FixtureTests(unittest.TestCase):
    def test_example_fixture_set_loads(self):
        fixture_set = load_fixture_set(FIXTURES)
        self.assertEqual(fixture_set["persona"]["persona_id"], "fictional-alex-river")
        self.assertEqual(len(fixture_set["postings"]), 3)
        self.assertEqual(len(fixture_set["route_decisions"]), 3)

    def test_fixture_decisions_never_submit(self):
        fixture_set = load_fixture_set(FIXTURES)
        self.assertTrue(
            all(
                decision["route"] != "submit"
                for decision in fixture_set["route_decisions"]
            )
        )

    def test_invalid_fixture_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            for filename in (
                "persona.json",
                "postings.json",
                "route_decisions.json",
            ):
                (destination / filename).write_bytes(
                    (FIXTURES / filename).read_bytes()
                )
            postings = (destination / "postings.json").read_text(encoding="utf-8")
            (destination / "postings.json").write_text(
                postings.replace("https://example.invalid/", "https://jobs.example/"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(FixtureError, "example.invalid"):
                load_fixture_set(destination)
