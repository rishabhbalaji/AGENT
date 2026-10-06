"""Isolation boundaries for creative Agent Corner work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class AgentCornerIsolationError(ValueError):
    """Raised when Agent Corner would overlap production state or credentials."""


@dataclass(frozen=True)
class AgentCornerPaths:
    """Dedicated paths for Agent Corner data and process state."""

    root: Path
    data: Path
    credentials: Path
    browser: Path
    jobs: Path
    lock: Path
    pause: Path

    @classmethod
    def from_root(cls, root: Path) -> "AgentCornerPaths":
        root = root.expanduser().resolve()
        return cls(
            root=root,
            data=root / "data",
            credentials=root / "credentials",
            browser=root / "browser",
            jobs=root / "jobs",
            lock=root / "agent-corner.lock",
            pause=root / "PAUSED",
        )


def validate_paths(paths: AgentCornerPaths, *, production_root: Path) -> None:
    """Reject paths that could expose production records or credentials."""
    production_root = production_root.expanduser().resolve()
    if paths.root == production_root or production_root.is_relative_to(paths.root):
        raise AgentCornerIsolationError(
            "Agent Corner root must not contain the production runtime root"
        )
    if paths.root.is_relative_to(production_root):
        raise AgentCornerIsolationError(
            "Agent Corner root must not be inside the production runtime root"
        )
    for path in (paths.credentials, paths.browser, paths.jobs):
        if not path.is_relative_to(paths.root):
            raise AgentCornerIsolationError("Agent Corner paths must remain under its root")


def prepare_paths(paths: AgentCornerPaths, *, production_root: Path) -> AgentCornerPaths:
    """Create only the isolated directories required by Agent Corner."""
    validate_paths(paths, production_root=production_root)
    for path in (paths.data, paths.credentials, paths.browser, paths.jobs):
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_artifact(
    paths: AgentCornerPaths,
    *,
    name: str,
    content: str,
) -> Path:
    """Write a named creative artifact inside the isolated data directory."""
    if not name or Path(name).name != name or name in {".", ".."}:
        raise AgentCornerIsolationError("artifact name must be a simple filename")
    destination = paths.data / name
    destination.write_text(content, encoding="utf-8")
    return destination
