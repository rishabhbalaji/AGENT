"""UK-local operating-mode resolution from schedule configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import ConfigurationError


class OperatingMode(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    MAINTENANCE = "maintenance"
    PAUSED = "paused"
    IDLE = "idle"


@dataclass(frozen=True)
class ModeState:
    mode: OperatingMode
    timezone: str
    actions: frozenset[str]
    matched_windows: tuple[str, ...]
    paused: bool = False

    def allows(self, action: str) -> bool:
        return not self.paused and action in self.actions


def _parse_time(value: object, window_name: str, field: str) -> time:
    if not isinstance(value, str):
        raise ConfigurationError(
            f"schedule.yaml: window '{window_name}.{field}' must be HH:MM"
        )
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"schedule.yaml: window '{window_name}.{field}' must be HH:MM"
        ) from exc


def _contains(now: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"schedule.yaml: unknown timezone '{name}'") from exc


def resolve_mode(
    schedule: dict[str, object],
    at: datetime,
    *,
    paused: bool = False,
) -> ModeState:
    """Resolve the schedule at an instant, converting naive times to its zone."""
    timezone_name = schedule.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ConfigurationError("schedule.yaml: timezone must be non-empty")
    zone = _timezone(timezone_name)
    local_at = at.replace(tzinfo=zone) if at.tzinfo is None else at.astimezone(zone)
    windows = schedule.get("windows")
    if not isinstance(windows, dict):
        raise ConfigurationError("schedule.yaml: windows must be a mapping")

    matches: list[tuple[str, frozenset[str]]] = []
    for name, raw_window in windows.items():
        if not isinstance(name, str) or not isinstance(raw_window, dict):
            raise ConfigurationError("schedule.yaml: each window must be a mapping")
        start = _parse_time(raw_window.get("start"), name, "start")
        end = _parse_time(raw_window.get("end"), name, "end")
        raw_actions = raw_window.get("allow")
        if not isinstance(raw_actions, list) or not all(
            isinstance(action, str) for action in raw_actions
        ):
            raise ConfigurationError(f"schedule.yaml: window '{name}.allow' must be a list")
        if _contains(local_at.time(), start, end):
            matches.append((name, frozenset(raw_actions)))

    actions = frozenset().union(*(actions for _, actions in matches))
    names = tuple(name for name, _ in matches)
    if paused:
        return ModeState(OperatingMode.PAUSED, timezone_name, frozenset(), names, True)

    if "part_time" in names:
        mode = OperatingMode.PART_TIME
    elif "full_time" in names:
        mode = OperatingMode.FULL_TIME
    elif "maintenance" in names:
        mode = OperatingMode.MAINTENANCE
    else:
        mode = OperatingMode.IDLE
    return ModeState(mode, timezone_name, actions, names)
