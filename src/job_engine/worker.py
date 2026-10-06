"""Bounded, lock-protected workers for unattended discovery."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import fcntl
from pathlib import Path

from .ollama import OllamaClient, OllamaConfig, OllamaError


@dataclass(frozen=True)
class WorkerResult:
    """Outcome of one bounded worker invocation."""

    status: str
    value: object | None = None


def set_pause(pause_path: Path) -> Path:
    """Create the explicit pause marker used by supervised workers."""
    pause_path = pause_path.expanduser()
    pause_path.parent.mkdir(parents=True, exist_ok=True)
    pause_path.touch(exist_ok=True)
    return pause_path


def clear_pause(pause_path: Path) -> Path:
    """Remove the explicit pause marker, if present."""
    pause_path = pause_path.expanduser()
    try:
        pause_path.unlink()
    except FileNotFoundError:
        pass
    return pause_path


def pause_status(pause_path: Path) -> bool:
    """Return whether the explicit pause marker currently exists."""
    return pause_path.expanduser().is_file()


def check_ollama_available(configuration: object, *, timeout_seconds: float = 10.0) -> None:
    """Require the exact configured Ollama endpoint and model before work."""
    policy = getattr(configuration, "policy", None)
    if not isinstance(policy, dict) or not isinstance(policy.get("ollama"), dict):
        raise OllamaError("Ollama policy is missing from configuration")
    settings = policy["ollama"]
    endpoint = settings.get("endpoint")
    model = settings.get("model")
    if not isinstance(endpoint, str) or not isinstance(model, str):
        raise OllamaError("Ollama policy has invalid endpoint or model")
    OllamaClient(OllamaConfig(endpoint, model, timeout_seconds)).check_health()


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

    def task() -> object:
        check_ollama_available(configuration)
        return discover_sources(
            adapters,
            configuration,
            database_path=database_path,
            dry_run=False,
        )

    return run_bounded_worker(
        task,
        lock_path=lock_path,
        pause_path=pause_path,
    )
