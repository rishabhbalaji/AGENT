import subprocess
import sys
import unittest

from job_engine import __version__
from job_engine.cli import build_parser, main


class PackageScaffoldTests(unittest.TestCase):
    def test_package_exposes_version(self):
        self.assertEqual(__version__, "0.1.0")

    def test_parser_has_expected_program_name(self):
        self.assertEqual(build_parser().prog, "job-engine")

    def test_main_accepts_log_level(self):
        self.assertEqual(main(["--log-level", "DEBUG"]), 0)

    def test_module_version_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "job_engine.cli", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("job-engine 0.1.0", result.stdout)
