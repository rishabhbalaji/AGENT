"""Bounded, lock-protected workers for unattended discovery."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import fcntl
from pathlib import Path


@dataclass(frozen=True)
class WorkerResult:
    """Outcome of one bounded worker invocation."""

    status: str
    value: object | None = None


def run_bounded_worker(
    task: Callable[[], object],
    *,
    lock_path: Path,
    pause_path: Path | None = None,
) -> WorkerResult:
    """Run one task unless paused or another invocation already holds the lock."""
    lock_path = lock_path.expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if pause_path is not None and pause_path.expanduser().exists():
        return WorkerResult("paused")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return WorkerResult("already_running")
        try:
            if pause_path is not None and pause_path.expanduser().exists():
                return WorkerResult("paused")
            return WorkerResult("completed", task())
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def run_discovery_worker(
    adapters: Sequence[object],
    configuration: object,
    *,
    database_path: Path,
    lock_path: Path,
    pause_path: Path | None = None,
) -> WorkerResult:
    """Run one persistent multi-source discovery pass under worker controls."""
    from .discovery import discover_sources

    return run_bounded_worker(
        lambda: discover_sources(
            adapters,
            configuration,
            database_path=database_path,
            dry_run=False,
        ),
        lock_path=lock_path,
        pause_path=pause_path,
    )
