import json
from unittest import TestCase
from unittest.mock import Mock, patch

from job_engine.ollama_benchmark import (
    BENCHMARK_FIELDS,
    benchmark_models,
    results_as_json,
)


class OllamaBenchmarkTests(TestCase):
    @patch("job_engine.ollama_benchmark.OllamaClient")
    def test_benchmark_validates_each_fixture_response(self, client_type: Mock) -> None:
        client = client_type.return_value
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.side_effect = [
            json.dumps(
                {
                    "role": "Junior Python Developer",
                    "seniority": "junior",
                    "sponsorship": "unknown",
                    "clearance_required": False,
                    "route": "draft_for_approval",
                }
            ),
            json.dumps(
                {
                    "role": "Python Developer",
                    "seniority": "unknown",
                    "sponsorship": "unknown",
                    "clearance_required": True,
                    "route": "park",
                }
            ),
        ]

        results = benchmark_models("http://example.invalid", ("fixture-model",))

        self.assertEqual(len(results), 2)
        self.assertEqual([result.status for result in results], ["passed", "passed"])
        self.assertEqual(results[1].route, "park")
        self.assertEqual(len(BENCHMARK_FIELDS), 5)

    @patch("job_engine.ollama_benchmark.OllamaClient")
    def test_malformed_response_fails_only_that_case(self, client_type: Mock) -> None:
        client = client_type.return_value
        client.check_health.return_value.model.digest = "sha256:test"
        client.generate_json.side_effect = ['{"route": "park"}', '{"bad": true}']

        results = benchmark_models("http://example.invalid", ("fixture-model",))

        self.assertEqual([result.status for result in results], ["failed", "failed"])
        self.assertTrue(all(not result.schema_valid for result in results))

    def test_results_are_json_serializable(self) -> None:
        self.assertEqual(results_as_json(()), "[]")
