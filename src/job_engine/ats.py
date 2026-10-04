"""Contracts shared by public job-source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlparse


class SourceContractError(ValueError):
    """Raised when an adapter returns data outside the source contract."""


class SourceHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class NormalizedPosting:
    """A source-independent representation of a public job posting."""

    source_name: str
    source_job_id: str
    title: str
    company: str
    source_url: str
    description: str
    location: str | None = None
    employment_type: str | None = None
    remote_mode: str | None = None
    posted_at: datetime | None = None
    closes_at: datetime | None = None
    requirements: tuple[str, ...] = ()
    clearance_requirements: tuple[str, ...] = ()
    raw_reference: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("source_name", "source_job_id", "title", "company", "description"):
            if not getattr(self, field_name).strip():
                raise SourceContractError(f"{field_name} must not be empty")
        parsed = urlparse(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SourceContractError("source_url must be an absolute HTTP(S) URL")
        if self.posted_at and self.posted_at.tzinfo is None:
            raise SourceContractError("posted_at must be timezone-aware")
        if self.closes_at and self.closes_at.tzinfo is None:
            raise SourceContractError("closes_at must be timezone-aware")
        if self.posted_at and self.closes_at and self.closes_at < self.posted_at:
            raise SourceContractError("closes_at must not precede posted_at")
        if any(not item.strip() for item in self.requirements):
            raise SourceContractError("requirements must not contain empty values")
        if any(not item.strip() for item in self.clearance_requirements):
            raise SourceContractError(
                "clearance_requirements must not contain empty values"
            )


@dataclass(frozen=True)
class RateLimit:
    """Adapter-declared request limit used by the future scheduler."""

    requests_per_minute: int
    burst: int = 1

    def __post_init__(self) -> None:
        if self.requests_per_minute < 1:
            raise SourceContractError("requests_per_minute must be positive")
        if self.burst < 1:
            raise SourceContractError("burst must be positive")


@dataclass(frozen=True)
class SourceHealth:
    """Observed health and fetch metadata for one source."""

    source_name: str
    status: SourceHealthStatus
    checked_at: datetime
    message: str = ""
    latency_ms: int | None = None
    records_seen: int = 0

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise SourceContractError("source_name must not be empty")
        if self.checked_at.tzinfo is None:
            raise SourceContractError("checked_at must be timezone-aware")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise SourceContractError("latency_ms must not be negative")
        if self.records_seen < 0:
            raise SourceContractError("records_seen must not be negative")


@dataclass(frozen=True)
class SourceFetchResult:
    """The result returned by one source adapter fetch."""

    postings: tuple[NormalizedPosting, ...]
    health: SourceHealth
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None:
            raise SourceContractError("fetched_at must be timezone-aware")
        if any(posting.source_name != self.health.source_name for posting in self.postings):
            raise SourceContractError(
                "all postings must belong to the result health source"
            )


class SourceAdapter(Protocol):
    """Interface implemented by each public, unauthenticated source adapter."""

    @property
    def name(self) -> str:
        """Return the stable source name used in configuration and records."""

    @property
    def rate_limit(self) -> RateLimit:
        """Return the adapter's declared request limit."""

    def fetch(self) -> SourceFetchResult:
        """Fetch and normalize public postings without requiring authentication."""
