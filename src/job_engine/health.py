"""Dry-run health checks for the local job application engine."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Configuration, load_config
from .database import record_event
from .modes import ModeState, resolve_mode
from .storage_check import MountInfo, validate_storage


StorageValidator = Callable[[Path], MountInfo]


def _parse_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("at must be an ISO-8601 datetime") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def run_health_check(
    *,
    config_dir: Path,
    data_root: Path,
    database_path: Path | None = None,
    at: datetime | None = None,
    paused: bool = False,
    storage_validator: StorageValidator = validate_storage,
) -> dict[str, Any]:
    """Validate local prerequisites and record one health event."""
    configuration: Configuration = load_config(config_dir)
    mount = storage_validator(data_root)
    mode: ModeState = resolve_mode(
        configuration.schedule,
        at or datetime.now(timezone.utc),
        paused=paused,
    )
    database = database_path or data_root / "engine.sqlite3"
    event_id = record_event(
        database,
        "health_check",
        entity_type="runtime",
        entity_id="local",
        payload_json=json.dumps(
            {
                "status": "ok",
                "mode": mode.mode.value,
                "matched_windows": mode.matched_windows,
            },
            sort_keys=True,
        ),
    )
    return {
        "status": "ok",
        "config_dir": str(config_dir),
        "data_root": str(data_root),
        "database": str(database),
        "mount_source": mount.source,
        "mode": mode.mode.value,
        "matched_windows": list(mode.matched_windows),
        "allowed_actions": sorted(mode.actions),
        "event_id": event_id,
    }


def run_health_from_strings(
    *,
    config_dir: Path,
    data_root: Path,
    database_path: Path | None = None,
    at: str | None = None,
    paused: bool = False,
    storage_validator: StorageValidator = validate_storage,
) -> dict[str, Any]:
    """CLI-friendly wrapper that parses an optional ISO-8601 timestamp."""
    return run_health_check(
        config_dir=config_dir,
        data_root=data_root,
        database_path=database_path,
        at=_parse_at(at),
        paused=paused,
        storage_validator=storage_validator,
    )
