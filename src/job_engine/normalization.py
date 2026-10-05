"""Deterministic normalization and deduplication for fetched postings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .ats import NormalizedPosting


class ExpirationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PostingRecord:
    """A normalized posting ready for policy filtering and persistence."""

    stable_id: str
    posting: NormalizedPosting
    fetched_at: datetime
    raw_snapshot: str
    expiration: ExpirationState
    is_repost: bool = False
    duplicate_count: int = 1

    @property
    def source_url(self) -> str:
        return self.posting.source_url

    @property
    def repost_key(self) -> str:
        return f"{self.posting.company.strip().casefold()}:{self.posting.title.strip().casefold()}"


def canonicalize_url(url: str) -> str:
    """Remove tracking query parameters while preserving the public URL."""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith(("utm_", "ref", "source"))
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            urlencode(query),
            "",
        )
    )


def stable_posting_id(posting: NormalizedPosting) -> str:
    """Derive a stable ID from the source identity, falling back to URL."""
    identity = posting.source_job_id.strip()
    if not identity:
        identity = canonicalize_url(posting.source_url)
    value = f"{posting.source_name.strip().casefold()}:{identity}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expiration(posting: NormalizedPosting, at: datetime) -> ExpirationState:
    if posting.closes_at is None:
        return ExpirationState.UNKNOWN
    return (
        ExpirationState.EXPIRED
        if posting.closes_at <= at
        else ExpirationState.ACTIVE
    )


def normalize_posting(
    posting: NormalizedPosting,
    *,
    fetched_at: datetime,
    at: datetime | None = None,
) -> PostingRecord:
    """Create a deterministic record while preserving source content."""
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    evaluated_at = at or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None:
        raise ValueError("at must be timezone-aware")
    raw_snapshot = posting.raw_reference or json.dumps(
        {
            "source_name": posting.source_name,
            "source_job_id": posting.source_job_id,
            "title": posting.title,
            "company": posting.company,
            "source_url": posting.source_url,
            "description": posting.description,
            "location": posting.location,
            "employment_type": posting.employment_type,
            "remote_mode": posting.remote_mode,
            "requirements": posting.requirements,
            "clearance_requirements": posting.clearance_requirements,
            "metadata": posting.metadata,
        },
        sort_keys=True,
        default=str,
    )
    return PostingRecord(
        stable_id=stable_posting_id(posting),
        posting=posting,
        fetched_at=fetched_at,
        raw_snapshot=raw_snapshot,
        expiration=_expiration(posting, evaluated_at),
    )


def deduplicate_postings(records: list[PostingRecord]) -> tuple[PostingRecord, ...]:
    """Keep the latest record for each stable ID and expose duplicate signals."""
    by_id: dict[str, PostingRecord] = {}
    counts: dict[str, int] = {}
    for record in records:
        counts[record.stable_id] = counts.get(record.stable_id, 0) + 1
        previous = by_id.get(record.stable_id)
        if previous is None or record.fetched_at >= previous.fetched_at:
            by_id[record.stable_id] = record

    result = [
        replace(
            record,
            is_repost=counts[record.stable_id] > 1,
            duplicate_count=counts[record.stable_id],
        )
        for record in by_id.values()
    ]
    return tuple(sorted(result, key=lambda record: record.stable_id))
