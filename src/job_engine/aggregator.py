"""Safety-gated adapter for explicitly approved guest job feeds."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .ats import (
    NormalizedPosting,
    RateLimit,
    SourceFetchResult,
    SourceHealth,
    SourceHealthStatus,
)
from .public_feed import PayloadFetcher


class GuestAggregatorAdapter:
    """Fetch a configured public JSON feed without authentication.

    The adapter is disabled unless explicitly enabled and the endpoint host is
    present in the caller-provided allowlist. It sends no cookies or secrets.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        allowed_hosts: frozenset[str] = frozenset(),
        enabled: bool = False,
        source_name: str = "guest_aggregator",
        rate_limit_per_minute: int = 5,
        timeout: float = 10.0,
        fetcher: PayloadFetcher | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        if not source_name.strip():
            raise ValueError("source_name must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if rate_limit_per_minute < 1:
            raise ValueError("rate_limit_per_minute must be positive")
        self._endpoint = endpoint
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._enabled = enabled
        self._source_name = source_name
        self._rate_limit = RateLimit(rate_limit_per_minute)
        self._timeout = timeout
        self._fetcher = fetcher

    @property
    def name(self) -> str:
        return self._source_name

    @property
    def rate_limit(self) -> RateLimit:
        return self._rate_limit

    def fetch(self) -> SourceFetchResult:
        checked_at = datetime.now(timezone.utc)
        host = urlparse(self._endpoint).hostname
        if not self._enabled:
            return self._result(
                checked_at,
                SourceHealthStatus.DISABLED,
                "guest aggregator is disabled by policy",
            )
        if host is None or host.lower() not in self._allowed_hosts:
            return self._result(
                checked_at,
                SourceHealthStatus.DISABLED,
                "endpoint host is not in the explicit guest allowlist",
            )
        if self._fetcher is None:
            return self._result(
                checked_at,
                SourceHealthStatus.DISABLED,
                "no public transport configured for guest aggregator",
            )
        try:
            payload, latency_ms = self._fetcher(self._endpoint, self._timeout)
            jobs = payload.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("guest feed response must contain a jobs list")
            postings = tuple(self._normalize(job) for job in jobs)
            health = SourceHealth(
                self.name,
                SourceHealthStatus.HEALTHY,
                checked_at,
                latency_ms=latency_ms,
                records_seen=len(postings),
            )
            return SourceFetchResult(postings, health, checked_at)
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return self._result(checked_at, SourceHealthStatus.UNAVAILABLE, str(exc))

    def _result(
        self,
        checked_at: datetime,
        status: SourceHealthStatus,
        message: str,
    ) -> SourceFetchResult:
        return SourceFetchResult(
            (),
            SourceHealth(self.name, status, checked_at, message=message),
            checked_at,
        )

    def _normalize(self, job: object) -> NormalizedPosting:
        if not isinstance(job, Mapping):
            raise ValueError("each guest feed job must be an object")
        required = ("id", "title", "company", "url", "description")
        values = {key: job.get(key) for key in required}
        if not all(isinstance(value, str) and value.strip() for value in values.values()):
            raise ValueError("guest feed jobs require id, title, company, url, and description")
        return NormalizedPosting(
            source_name=self.name,
            source_job_id=values["id"].strip(),
            title=values["title"].strip(),
            company=values["company"].strip(),
            source_url=values["url"].strip(),
            description=values["description"].strip(),
            location=job.get("location") if isinstance(job.get("location"), str) else None,
            raw_reference=json.dumps(dict(job), sort_keys=True),
        )
