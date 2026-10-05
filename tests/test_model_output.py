import unittest
from datetime import datetime, timezone

from job_engine.model_output import (
    ModelOutputValidationError,
    ModelProvenance,
    parse_model_output,
    validate_model_output,
)


PROVENANCE = ModelProvenance(
    prompt="Summarize the posting.",
    model="fixture-model",
    model_version="1.0",
    revision="prompt-rev-1",
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)


class ModelOutputTests(unittest.TestCase):
    def test_valid_output_preserves_schema_and_provenance(self):
        output = validate_model_output(
            {"summary": "A concise summary."},
            schema_name="job_summary",
            schema_version=1,
            required_fields=("summary",),
            allowed_fields=("summary",),
            provenance=PROVENANCE,
        )
        self.assertEqual(output.payload["summary"], "A concise summary.")
        self.assertEqual(output.provenance.revision, "prompt-rev-1")

    def test_unknown_and_missing_fields_are_rejected(self):
        with self.assertRaises(ModelOutputValidationError):
            validate_model_output(
                {"summary": "ok", "extra": True},
                schema_name="job_summary",
                schema_version=1,
                required_fields=("summary",),
                allowed_fields=("summary",),
                provenance=PROVENANCE,
            )
        with self.assertRaises(ModelOutputValidationError):
            validate_model_output(
                {},
                schema_name="job_summary",
                schema_version=1,
                required_fields=("summary",),
                allowed_fields=("summary",),
                provenance=PROVENANCE,
            )

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ModelOutputValidationError):
            parse_model_output(
                "{not-json}",
                schema_name="job_summary",
                schema_version=1,
                required_fields=("summary",),
                allowed_fields=("summary",),
                provenance=PROVENANCE,
            )

    def test_provenance_requires_timezone_and_non_empty_values(self):
        with self.assertRaises(ModelOutputValidationError):
            ModelProvenance(
                prompt="",
                model="fixture-model",
                model_version="1.0",
                revision="rev",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        with self.assertRaises(ModelOutputValidationError):
            ModelProvenance(
                prompt="Prompt",
                model="fixture-model",
                model_version="1.0",
                revision="rev",
                created_at=datetime(2026, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
