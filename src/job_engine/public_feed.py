"""Fixture-friendly adapters for public JSON job feeds."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
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
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "job-engine/0.1"},
    )
    started = time.monotonic()
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("public feed response root must be an object")
    return payload, int((time.monotonic() - started) * 1000)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class GovUkFindAJobAdapter:
    """Read a public JSON representation of GOV.UK Find a Job results.

    The endpoint is injected/configured so the adapter does not guess at an
    undocumented endpoint and tests never require network access.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        timeout: float = 10.0,
        fetcher: PayloadFetcher = _fetch_json,
    ) -> None:
        if not endpoint.startswith(("https://", "http://")):
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._endpoint = endpoint
        self._timeout = timeout
        self._fetcher = fetcher

    @property
    def name(self) -> str:
        return "govuk_find_a_job"

    @property
    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=10)

    def fetch(self) -> SourceFetchResult:
        fetched_at = datetime.now(timezone.utc)
        try:
            payload, latency_ms = self._fetcher(self._endpoint, self._timeout)
            raw_jobs = payload.get("jobs")
            if not isinstance(raw_jobs, list):
                raise ValueError("public feed response must contain a jobs list")
            postings = tuple(self._normalize(job) for job in raw_jobs)
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

    def _normalize(self, job: object) -> NormalizedPosting:
        if not isinstance(job, dict):
            raise ValueError("each public feed job must be an object")
        job_id = _text(job.get("id"))
        title = _text(job.get("title"))
        company = _text(job.get("company"))
        source_url = _text(job.get("url"))
        description = _text(job.get("description"))
        if not all((job_id, title, company, source_url, description)):
            raise ValueError("public feed jobs require id, title, company, url, and description")
        return NormalizedPosting(
            source_name=self.name,
            source_job_id=job_id,
            title=title,
            company=company,
            source_url=source_url,
            description=description,
            location=_text(job.get("location")) or None,
            employment_type=_text(job.get("employment_type")) or None,
            remote_mode=_text(job.get("remote_mode")) or None,
            posted_at=_date(job.get("posted_at")),
            closes_at=_date(job.get("closes_at")),
            requirements=tuple(
                item for item in job.get("requirements", []) if isinstance(item, str)
            ),
            clearance_requirements=tuple(
                item
                for item in job.get("clearance_requirements", [])
                if isinstance(item, str)
            ),
            raw_reference=json.dumps(job, sort_keys=True),
        )
