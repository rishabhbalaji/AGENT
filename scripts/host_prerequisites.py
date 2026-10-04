#!/usr/bin/env python3
"""Report host prerequisites without changing the machine."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


CommandFinder = Callable[[str], str | None]


def check_command(name: str, finder: CommandFinder = shutil.which) -> CheckResult:
    path = finder(name)
    return CheckResult(name, path is not None, path or "not found")


def check_python(minimum: tuple[int, int] = (3, 12)) -> CheckResult:
    current = sys.version_info[:2]
    required = ".".join(str(part) for part in minimum)
    version = ".".join(str(part) for part in current)
    return CheckResult(
        "python",
        current >= minimum,
        f"{version} (requires >= {required})",
    )


def check_ollama(
    url: str,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> CheckResult:
    endpoint = url.rstrip("/") + "/api/tags"
    try:
        with opener(endpoint, timeout=3):
            return CheckResult("ollama", True, endpoint)
    except (OSError, urllib.error.URLError) as exc:
        return CheckResult("ollama", False, f"{endpoint}: {exc}")


def collect_checks(
    *,
    ollama_url: str | None = None,
    finder: CommandFinder = shutil.which,
    python_minimum: tuple[int, int] = (3, 12),
) -> list[CheckResult]:
    checks = [
        check_python(python_minimum),
        check_command("systemctl", finder),
        check_command("findmnt", finder),
        check_command("tailscale", finder),
        CheckResult(
            "pdf-tool",
            any(finder(name) for name in ("tectonic", "pdflatex")),
            "tectonic or pdflatex",
        ),
    ]
    if ollama_url:
        checks.append(check_ollama(ollama_url))
    return checks


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ollama-url",
        help="Optionally check the configured Ollama endpoint.",
    )
    args = parser.parse_args(argv)
    checks = collect_checks(ollama_url=args.ollama_url)
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status:<4} {check.name}: {check.detail}")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
