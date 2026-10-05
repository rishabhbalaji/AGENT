import json
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import URLError

from job_engine.ollama import OllamaClient, OllamaConfig, OllamaError


class OllamaClientTests(TestCase):
    def setUp(self) -> None:
        self.client = OllamaClient(OllamaConfig("http://100.64.0.10:11434", "qwen2.5:7b"))

    @patch("job_engine.ollama.urlopen")
    def test_health_requires_exact_configured_model(self, urlopen: Mock) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        response.read.return_value = json.dumps(
            {
                "models": [
                    {
                        "name": "qwen2.5:7b",
                        "digest": "sha256:test",
                        "modified_at": "2026-10-05T00:00:00Z",
                    }
                ]
            }
        ).encode()
        urlopen.return_value = response

        health = self.client.check_health()

        self.assertEqual(health.model.name, "qwen2.5:7b")
        self.assertEqual(health.model.digest, "sha256:test")

    @patch("job_engine.ollama.urlopen")
    def test_health_fails_when_model_is_missing(self, urlopen: Mock) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        response.read.return_value = b'{"models": []}'
        urlopen.return_value = response

        with self.assertRaisesRegex(OllamaError, "unavailable"):
            self.client.check_health()

    @patch("job_engine.ollama.urlopen")
    def test_generate_json_requests_non_streaming_json(self, urlopen: Mock) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        response.read.return_value = b'{"message": {"content": "{\\"fit\\": 82}"}}'
        urlopen.return_value = response

        result = self.client.generate_json("Assess this fictional job.")

        self.assertEqual(result, '{"fit": 82}')
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode())
        self.assertEqual(payload["model"], "qwen2.5:7b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")

    @patch("job_engine.ollama.urlopen", side_effect=URLError("offline"))
    def test_request_failure_is_fail_closed(self, _urlopen: Mock) -> None:
        with self.assertRaisesRegex(OllamaError, "failed"):
            self.client.list_models()
