"""Schedule and queue gates for the large-context deep-review worker."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import sqlite3
from pathlib import Path

from .config import Configuration
from .modes import resolve_mode
from .ollama import OllamaClient, OllamaConfig
from .worker import WorkerResult, run_bounded_worker


ACTIONABLE_STATUSES = ("drafted", "shortlisted", "apply_yourself")


def actionable_queue_depth(database_path: Path) -> int:
    """Count jobs that still need ordinary human review or action."""
    try:
        with sqlite3.connect(database_path.expanduser()) as connection:
            placeholders = ", ".join("?" for _ in ACTIONABLE_STATUSES)
            row = connection.execute(
                f"SELECT COUNT(*) FROM jobs WHERE status IN ({placeholders})",
                ACTIONABLE_STATUSES,
            ).fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot read actionable queue: {exc}") from exc
    return int(row[0]) if row else 0


def deep_review_is_allowed(
    configuration: Configuration,
    *,
    actionable_depth: int,
    at: datetime,
    paused: bool = False,
) -> bool:
    """Return whether the deep-review window and queue gate both permit work."""
    if actionable_depth < 0:
        raise ValueError("actionable_depth must be non-negative")
    state = resolve_mode(configuration.schedule, at, paused=paused)
    limit = configuration.policy["deep_review"]["max_actionable_queue_depth"]
    return state.allows("deep_review") and actionable_depth <= limit


def deep_review_model(configuration: Configuration) -> str:
    """Return the explicitly configured large-context model."""
    settings = configuration.policy["ollama"]
    model = settings.get("deep_review_model", "qwen3-coder-64k:latest")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("deep review model must be non-empty")
    return model


def run_deep_review_worker(
    task: Callable[[], object],
    configuration: Configuration,
    *,
    database_path: Path,
    lock_path: Path,
    at: datetime,
    pause_path: Path | None = None,
) -> WorkerResult:
    """Run deep review only inside its UK window and an empty actionable queue."""
    def guarded_task() -> object:
        settings = configuration.policy["ollama"]
        endpoint = settings["endpoint"]
        client = OllamaClient(
            OllamaConfig(endpoint, deep_review_model(configuration), timeout_seconds=10.0)
        )
        client.check_health()
        return task()

    if pause_path is not None and pause_path.expanduser().exists():
        return WorkerResult("paused")
    depth = actionable_queue_depth(database_path)
    if not deep_review_is_allowed(configuration, actionable_depth=depth, at=at):
        return WorkerResult("not_eligible", {"actionable_queue_depth": depth})
    return run_bounded_worker(guarded_task, lock_path=lock_path, pause_path=pause_path)
