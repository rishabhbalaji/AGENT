import unittest

from scripts.host_prerequisites import (
    CheckResult,
    check_command,
    check_ollama,
    collect_checks,
)


class HostPrerequisiteTests(unittest.TestCase):
    def test_check_command_reports_path(self):
        result = check_command("systemctl", lambda _: "/usr/bin/systemctl")
        self.assertEqual(result, CheckResult("systemctl", True, "/usr/bin/systemctl"))

    def test_check_command_reports_missing_command(self):
        result = check_command("tailscale", lambda _: None)
        self.assertEqual(result, CheckResult("tailscale", False, "not found"))

    def test_collect_checks_does_not_probe_ollama_without_url(self):
        checks = collect_checks(finder=lambda _: "/usr/bin/tool")
        self.assertNotIn("ollama", {check.name for check in checks})

    def test_ollama_success(self):
        result = check_ollama(
            "http://ollama.example",
            opener=lambda endpoint, timeout: _Response(endpoint, timeout),
        )
        self.assertTrue(result.passed)
        self.assertIn("/api/tags", result.detail)

    def test_ollama_failure(self):
        def fail(*_, **__):
            raise OSError("unreachable")

        result = check_ollama("http://ollama.example", opener=fail)
        self.assertFalse(result.passed)
        self.assertIn("unreachable", result.detail)


class _Response:
    def __init__(self, endpoint, timeout):
        self.endpoint = endpoint
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False
