"""Unauthenticated adapter for Greenhouse-compatible public job boards."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .ats import (
    NormalizedPosting,
    RateLimit,
    SourceFetchResult,
    SourceHealth,
    SourceHealthStatus,
)


PayloadFetcher = Callable[[str, float], tuple[dict[str, Any], int]]


def _fetch_json(url: str, timeout: float) -> tuple[dict[str, Any], int]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "job-engine/0.1"})
    started = time.monotonic()
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
        latency_ms = int((time.monotonic() - started) * 1000)
    if not isinstance(payload, dict):
        raise ValueError("Greenhouse response root must be an object")
    return payload, latency_ms


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _posting(job: dict[str, Any], source_name: str) -> NormalizedPosting:
    job_id = job.get("id")
    title = _text(job.get("title"))
    source_url = _text(job.get("absolute_url"))
    location = job.get("location")
    location_name = location.get("name") if isinstance(location, dict) else None
    content = _text(job.get("content"))
    if not isinstance(job_id, int | str) or not title or not source_url or not content:
        raise ValueError("Greenhouse job requires id, title, absolute_url, and content")
    return NormalizedPosting(
        source_name=source_name,
        source_job_id=str(job_id),
        title=title,
        company=_text(job.get("company_name")) or source_name,
        source_url=source_url,
        description=content,
        location=_text(location_name) or None,
        posted_at=_parse_datetime(job.get("updated_at")),
        raw_reference=json.dumps(job, sort_keys=True),
        metadata={"board_job_id": str(job_id)},
    )


class GreenhouseAdapter:
    """Fetch public Greenhouse jobs for one board slug."""

    def __init__(
        self,
        board_slug: str,
        *,
        source_name: str = "greenhouse",
        timeout: float = 10.0,
        fetcher: PayloadFetcher = _fetch_json,
    ) -> None:
        if not board_slug.strip():
            raise ValueError("board_slug must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._board_slug = board_slug.strip()
        self._source_name = source_name
        self._timeout = timeout
        self._fetcher = fetcher

    @property
    def name(self) -> str:
        return self._source_name

    @property
    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=30)

    @property
    def url(self) -> str:
        slug = quote(self._board_slug, safe="")
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

    def fetch(self) -> SourceFetchResult:
        fetched_at = datetime.now(timezone.utc)
        try:
            payload, latency_ms = self._fetcher(self.url, self._timeout)
            raw_jobs = payload.get("jobs")
            if not isinstance(raw_jobs, list):
                raise ValueError("Greenhouse response must contain a jobs list")
            postings = tuple(
                _posting(job, self.name)
                for job in raw_jobs
                if isinstance(job, dict)
            )
            health = SourceHealth(
                self.name,
                SourceHealthStatus.HEALTHY,
                fetched_at,
                latency_ms=latency_ms,
                records_seen=len(postings),
            )
            return SourceFetchResult(postings, health, fetched_at)
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            health = SourceHealth(
                self.name,
                SourceHealthStatus.UNAVAILABLE,
                fetched_at,
                message=str(exc),
            )
            return SourceFetchResult((), health, fetched_at)
