"""Typed loading and validation for the engine's local YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILES = (
    "profiles.yaml",
    "schedule.yaml",
    "sources.yaml",
    "repositories.yaml",
    "policy.yaml",
)


class ConfigurationError(ValueError):
    """Raised when local configuration cannot be loaded safely."""


@dataclass(frozen=True)
class Configuration:
    """Validated configuration documents keyed by their filename stem."""

    profiles: dict[str, Any]
    schedule: dict[str, Any]
    sources: dict[str, Any]
    repositories: dict[str, Any]
    policy: dict[str, Any]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "profiles": self.profiles,
            "schedule": self.schedule,
            "sources": self.sources,
            "repositories": self.repositories,
            "policy": self.policy,
        }


def _load_document(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
    except OSError as exc:
        raise ConfigurationError(f"{path.name}: cannot read file: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path.name}: invalid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise ConfigurationError(f"{path.name}: root must be a mapping")
    if document.get("version") != 1:
        raise ConfigurationError(f"{path.name}: version must be 1")
    return document


def _require_mapping(document: dict[str, Any], key: str, filename: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{filename}: '{key}' must be a mapping")
    return value


def _require_list(document: dict[str, Any], key: str, filename: str) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list):
        raise ConfigurationError(f"{filename}: '{key}' must be a list")
    return value


def _validate_profiles(document: dict[str, Any]) -> None:
    profiles = _require_mapping(document, "profiles", "profiles.yaml")
    if not profiles:
        raise ConfigurationError("profiles.yaml: at least one profile is required")
    for name, profile in profiles.items():
        if not isinstance(name, str) or not isinstance(profile, dict):
            raise ConfigurationError("profiles.yaml: each profile must be a mapping")
        for key in ("enabled", "employment_types", "keywords", "locations", "remote", "salary", "score_threshold", "schedule"):
            if key not in profile:
                raise ConfigurationError(f"profiles.yaml: profile '{name}' is missing '{key}'")
        if not isinstance(profile["enabled"], bool):
            raise ConfigurationError(f"profiles.yaml: profile '{name}.enabled' must be boolean")
        if not isinstance(profile["score_threshold"], int) or not 0 <= profile["score_threshold"] <= 100:
            raise ConfigurationError(f"profiles.yaml: profile '{name}.score_threshold' must be 0-100")
        _require_mapping(profile, "keywords", "profiles.yaml")
        _require_mapping(profile, "locations", "profiles.yaml")
        _require_mapping(profile, "remote", "profiles.yaml")
        _require_mapping(profile, "salary", "profiles.yaml")
        _require_mapping(profile, "schedule", "profiles.yaml")


def _validate_schedule(document: dict[str, Any]) -> None:
    windows = _require_mapping(document, "windows", "schedule.yaml")
    if not windows:
        raise ConfigurationError("schedule.yaml: at least one window is required")
    if not isinstance(document.get("timezone"), str) or not document["timezone"]:
        raise ConfigurationError("schedule.yaml: timezone must be non-empty")
    _require_mapping(document, "pause", "schedule.yaml")


def _validate_sources(document: dict[str, Any]) -> None:
    sources = _require_mapping(document, "sources", "sources.yaml")
    for name, source in sources.items():
        if not isinstance(source, dict):
            raise ConfigurationError(f"sources.yaml: source '{name}' must be a mapping")
        if not isinstance(source.get("enabled"), bool):
            raise ConfigurationError(f"sources.yaml: source '{name}.enabled' must be boolean")
        if source.get("authentication") in {"cookies", "login", "session"}:
            raise ConfigurationError(
                f"sources.yaml: authenticated access is forbidden for '{name}'"
            )
    _require_mapping(document, "policy", "sources.yaml")


def _validate_repositories(document: dict[str, Any]) -> None:
    for repository in _require_list(document, "repositories", "repositories.yaml"):
        if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
            raise ConfigurationError(
                "repositories.yaml: repositories must be HTTPS GitHub URLs"
            )


def _validate_policy(document: dict[str, Any]) -> None:
    storage = _require_mapping(document, "storage", "policy.yaml")
    discovery = _require_mapping(document, "discovery", "policy.yaml")
    ollama = _require_mapping(document, "ollama", "policy.yaml")
    deep_review = _require_mapping(document, "deep_review", "policy.yaml")
    clearance = _require_mapping(document, "clearance", "policy.yaml")
    applications = _require_mapping(document, "applications", "policy.yaml")
    _require_mapping(document, "retention", "policy.yaml")
    company_exclusions = _require_list(document, "company_exclusions", "policy.yaml")
    if storage.get("require_sda_device") is not True:
        raise ConfigurationError("policy.yaml: SDA storage must be required")
    if discovery.get("suitable_jobs_target_per_day") != 15:
        raise ConfigurationError("policy.yaml: suitable jobs target must be 15")
    if ollama.get("required_for_engine") is not True:
        raise ConfigurationError("policy.yaml: Ollama must be required for the engine")
    if not isinstance(ollama.get("endpoint"), str) or not ollama["endpoint"].strip():
        raise ConfigurationError("policy.yaml: Ollama endpoint must be non-empty")
    if not isinstance(ollama.get("model"), str) or not ollama["model"].strip():
        raise ConfigurationError("policy.yaml: Ollama model must be non-empty")
    if "deep_review_model" in ollama and (
        not isinstance(ollama["deep_review_model"], str)
        or not ollama["deep_review_model"].strip()
    ):
        raise ConfigurationError("policy.yaml: deep review model must be non-empty")
    queue_depth = deep_review.get("max_actionable_queue_depth")
    if not isinstance(queue_depth, int) or queue_depth < 0:
        raise ConfigurationError(
            "policy.yaml: deep review queue depth must be a non-negative integer"
        )
    if not _require_list(clearance, "exclude_required_or_requested", "policy.yaml"):
        raise ConfigurationError("policy.yaml: clearance exclusions cannot be empty")
    for exclusion in company_exclusions:
        if not isinstance(exclusion, dict):
            raise ConfigurationError("policy.yaml: company exclusions must be mappings")
        if not isinstance(exclusion.get("name"), str) or not exclusion["name"].strip():
            raise ConfigurationError("policy.yaml: company exclusion names must be non-empty")
        if not isinstance(exclusion.get("aliases", []), list):
            raise ConfigurationError("policy.yaml: company exclusion aliases must be a list")
        if not isinstance(exclusion.get("domains", []), list):
            raise ConfigurationError("policy.yaml: company exclusion domains must be a list")
        if not isinstance(exclusion.get("reason"), str) or not exclusion["reason"].strip():
            raise ConfigurationError("policy.yaml: company exclusion reasons must be non-empty")
    if applications.get("default_mode") != "approval_required":
        raise ConfigurationError("policy.yaml: default application mode must require approval")


def load_config(config_dir: Path) -> Configuration:
    """Load and validate the complete configuration directory."""
    config_dir = config_dir.expanduser()
    documents: dict[str, dict[str, Any]] = {}
    for filename in CONFIG_FILES:
        path = config_dir / filename
        if not path.is_file():
            raise ConfigurationError(f"{filename}: file is missing from {config_dir}")
        documents[Path(filename).stem] = _load_document(path)

    _validate_profiles(documents["profiles"])
    _validate_schedule(documents["schedule"])
    _validate_sources(documents["sources"])
    _validate_repositories(documents["repositories"])
    _validate_policy(documents["policy"])
    return Configuration(**documents)
