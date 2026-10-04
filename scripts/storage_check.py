#!/usr/bin/env python3
"""Fail-closed validation for the engine's SDA-backed data root."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch


class StorageCheckError(RuntimeError):
    """Raised when the configured data root is unsafe to use."""


@dataclass(frozen=True)
class MountInfo:
    source: str
    options: frozenset[str]


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def parse_mount_info(output: str) -> MountInfo:
    """Parse the SOURCE and OPTIONS fields returned by findmnt."""
    fields = output.strip().split(maxsplit=1)
    if len(fields) != 2 or not fields[0] or not fields[1]:
        raise StorageCheckError("findmnt returned incomplete mount metadata")
    return MountInfo(
        source=fields[0],
        options=frozenset(option for option in fields[1].split(",") if option),
    )


def _run_findmnt(data_root: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                "findmnt",
                "--noheadings",
                "--output",
                "SOURCE,OPTIONS",
                "--target",
                str(data_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise StorageCheckError(f"unable to execute findmnt: {exc}") from exc


def _mount_info(data_root: Path, runner: Runner) -> MountInfo:
    result = runner(data_root)
    if result.returncode != 0:
        detail = result.stderr.strip() or "no mount metadata returned"
        raise StorageCheckError(f"cannot resolve data-root mount: {detail}")
    return parse_mount_info(result.stdout)


def _source_is_sda(source: str) -> bool:
    resolved = os.path.realpath(source)
    return bool(fullmatch(r"/dev/sda\d+", resolved)) or resolved == "/dev/sda"


def validate_storage(
    data_root: Path,
    *,
    expected_device_prefix: str = "/dev/sda",
    runner: Runner = _run_findmnt,
) -> MountInfo:
    """Validate the data root and return its mount metadata.

    The default expected device is SDA. Callers may inject a stricter expected
    device prefix for host-specific validation, but must not use `/dev/sdb`.
    """
    data_root = data_root.expanduser()
    if expected_device_prefix == "/dev/sdb":
        raise StorageCheckError("the engine must not use /dev/sdb")
    if not data_root.exists():
        raise StorageCheckError(f"data root does not exist: {data_root}")
    if not data_root.is_dir():
        raise StorageCheckError(f"data root is not a directory: {data_root}")
    if not os.access(data_root, os.R_OK | os.X_OK | os.W_OK):
        raise StorageCheckError(f"data root is not writable: {data_root}")

    mount = _mount_info(data_root, runner)
    if "ro" in mount.options:
        raise StorageCheckError(f"data root is mounted read-only: {data_root}")
    resolved_source = os.path.realpath(mount.source)
    if expected_device_prefix == "/dev/sda":
        source_matches = _source_is_sda(mount.source)
    else:
        expected = os.path.realpath(expected_device_prefix)
        source_matches = resolved_source == expected
    if not source_matches:
        raise StorageCheckError(
            f"data root is on {mount.source}, expected a filesystem on "
            f"{expected_device_prefix}"
        )

    try:
        with tempfile.NamedTemporaryFile(
            dir=data_root, prefix=".storage-check-", delete=True
        ):
            pass
    except OSError as exc:
        raise StorageCheckError(f"cannot write to data root {data_root}: {exc}") from exc
    return mount


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    parser.add_argument("--expected-device", default="/dev/sda")
    args = parser.parse_args(argv)
    try:
        mount = validate_storage(
            args.data_root, expected_device_prefix=args.expected_device
        )
    except StorageCheckError as exc:
        print(f"storage check failed: {exc}", file=sys.stderr)
        return 1
    print(f"storage check passed: {args.data_root} ({mount.source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
