import tempfile
import unittest
from pathlib import Path

from job_engine.ats_fixtures import ATSFixtureError, load_form_fixture


ROOT = Path(__file__).resolve().parents[1]


class ATSFixtureTests(unittest.TestCase):
    def test_greenhouse_form_fixture_loads_and_validates_answers(self):
        fixture = load_form_fixture(ROOT / "fixtures" / "greenhouse_application_form.json")
        self.assertEqual(fixture.provider, "greenhouse")
        self.assertEqual(fixture.required_field_names(), ("name", "email", "resume", "work_authorisation"))
        fixture.validate_answers(
            {
                "name": "Alex River",
                "email": "alex@example.invalid",
                "resume": "resume.pdf",
                "work_authorisation": "Yes",
            }
        )

    def test_required_and_select_answers_are_enforced(self):
        fixture = load_form_fixture(ROOT / "fixtures" / "greenhouse_application_form.json")
        with self.assertRaisesRegex(ATSFixtureError, "missing required"):
            fixture.validate_answers({"name": "Alex River"})
        with self.assertRaisesRegex(ATSFixtureError, "invalid option"):
            fixture.validate_answers(
                {
                    "name": "Alex River",
                    "email": "alex@example.invalid",
                    "resume": "resume.pdf",
                    "work_authorisation": "Maybe",
                }
            )

    def test_live_urls_and_unknown_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(
                '{"provider":"greenhouse","job_id":"1",'
                '"application_url":"https://jobs.example/apply","fields":'
                '[{"name":"name","label":"Name","type":"text","required":true}]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ATSFixtureError, "example.invalid"):
                load_form_fixture(path)
