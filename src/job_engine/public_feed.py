"""Fixture-friendly adapters for public JSON job feeds."""

from __future__ import annotations

import json
import time
from base64 import b64encode
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .ats import (
    NormalizedPosting,
    RateLimit,
    SourceFetchResult,
    SourceHealth,
    SourceHealthStatus,
)


PayloadFetcher = Callable[[str, float], tuple[dict[str, Any], int]]


def _fetch_json(
    url: str,
    timeout: float,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], int]:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "job-engine/0.1",
        **(headers or {}),
    }
    request = Request(url, headers=request_headers)
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


class _ApiFeedAdapter:
    """Shared safety and health behavior for explicitly credentialed feeds."""

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None,
        timeout: float,
        fetcher: PayloadFetcher,
    ) -> None:
        if not endpoint.startswith(("https://", "http://")):
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._endpoint = endpoint
        self._api_key = api_key.strip() if isinstance(api_key, str) else None
        self._timeout = timeout
        self._fetcher = fetcher

    def _disabled(self, checked_at: datetime, message: str) -> SourceFetchResult:
        return SourceFetchResult(
            (),
            SourceHealth(self.name, SourceHealthStatus.DISABLED, checked_at, message=message),
            checked_at,
        )

    def _fetch(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], int]:
        if headers and self._fetcher is _fetch_json:
            return _fetch_json(url, self._timeout, headers=headers)
        return self._fetcher(url, self._timeout)


class ReedAdapter(_ApiFeedAdapter):
    """Fetch Reed search results only when an explicit API key is supplied."""

    def __init__(
        self,
        endpoint: str = "https://www.reed.co.uk/api/1.0/search",
        *,
        api_key: str | None = None,
        keywords: str = "",
        location: str = "",
        timeout: float = 10.0,
        fetcher: PayloadFetcher = _fetch_json,
    ) -> None:
        super().__init__(
            endpoint,
            api_key=api_key,
            timeout=timeout,
            fetcher=fetcher,
        )
        if not keywords.strip():
            raise ValueError("keywords must not be empty")
        self._keywords = keywords.strip()
        self._location = location.strip()

    @property
    def name(self) -> str:
        return "reed"

    @property
    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=10)

    def fetch(self) -> SourceFetchResult:
        checked_at = datetime.now(timezone.utc)
        if not self._api_key:
            return self._disabled(checked_at, "Reed API key is not configured")
        query = urlencode({"keywords": self._keywords, "locationName": self._location})
        url = f"{self._endpoint}?{query}"
        credentials = b64encode(f"{self._api_key}:".encode()).decode("ascii")
        try:
            payload, latency_ms = self._fetch(
                url,
                headers={"Authorization": f"Basic {credentials}"},
            )
            jobs = payload.get("results")
            if not isinstance(jobs, list):
                raise ValueError("Reed response must contain a results list")
            postings = tuple(self._normalize(job) for job in jobs)
            return SourceFetchResult(
                postings,
                SourceHealth(
                    self.name,
                    SourceHealthStatus.HEALTHY,
                    checked_at,
                    latency_ms=latency_ms,
                    records_seen=len(postings),
                ),
                checked_at,
            )
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return SourceFetchResult(
                (),
                SourceHealth(self.name, SourceHealthStatus.UNAVAILABLE, checked_at, message=str(exc)),
                checked_at,
            )

    def _normalize(self, job: object) -> NormalizedPosting:
        if not isinstance(job, dict):
            raise ValueError("each Reed job must be an object")
        job_id = str(job.get("jobId", "")).strip()
        title = _text(job.get("jobTitle"))
        company = _text(job.get("employerName"))
        source_url = _text(job.get("jobUrl"))
        description = _text(job.get("jobDescription"))
        if not all((job_id, title, company, source_url, description)):
            raise ValueError("Reed jobs require jobId, jobTitle, employerName, jobUrl, and jobDescription")
        return NormalizedPosting(
            source_name=self.name,
            source_job_id=job_id,
            title=title,
            company=company,
            source_url=source_url,
            description=description,
            location=_text(job.get("locationName")) or None,
            employment_type=_text(job.get("contractType")) or None,
            posted_at=_date(job.get("date")),
            closes_at=_date(job.get("expirationDate")),
            raw_reference=json.dumps(job, sort_keys=True),
        )


class AdzunaAdapter(_ApiFeedAdapter):
    """Fetch Adzuna UK search results only with explicit application credentials."""

    def __init__(
        self,
        endpoint: str = "https://api.adzuna.com/v1/api/jobs/gb/search/1",
        *,
        app_id: str | None = None,
        app_key: str | None = None,
        keywords: str = "",
        location: str = "",
        timeout: float = 10.0,
        fetcher: PayloadFetcher = _fetch_json,
    ) -> None:
        super().__init__(
            endpoint,
            api_key=app_key,
            timeout=timeout,
            fetcher=fetcher,
        )
        self._app_id = app_id.strip() if isinstance(app_id, str) else None
        self._keywords = keywords.strip()
        self._location = location.strip()

    @property
    def name(self) -> str:
        return "adzuna"

    @property
    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=10)

    def fetch(self) -> SourceFetchResult:
        checked_at = datetime.now(timezone.utc)
        if not self._app_id or not self._api_key:
            return self._disabled(checked_at, "Adzuna app_id and app_key are not configured")
        query = urlencode(
            {
                "app_id": self._app_id,
                "app_key": self._api_key,
                "what": self._keywords,
                "where": self._location,
                "results_per_page": 50,
            }
        )
        try:
            payload, latency_ms = self._fetch(f"{self._endpoint}?{query}")
            jobs = payload.get("results")
            if not isinstance(jobs, list):
                raise ValueError("Adzuna response must contain a results list")
            postings = tuple(self._normalize(job) for job in jobs)
            return SourceFetchResult(
                postings,
                SourceHealth(
                    self.name,
                    SourceHealthStatus.HEALTHY,
                    checked_at,
                    latency_ms=latency_ms,
                    records_seen=len(postings),
                ),
                checked_at,
            )
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return SourceFetchResult(
                (),
                SourceHealth(self.name, SourceHealthStatus.UNAVAILABLE, checked_at, message=str(exc)),
                checked_at,
            )

    def _normalize(self, job: object) -> NormalizedPosting:
        if not isinstance(job, dict):
            raise ValueError("each Adzuna job must be an object")
        job_id = str(job.get("id", "")).strip()
        title = _text(job.get("title"))
        company = job.get("company")
        company_name = _text(company.get("display_name")) if isinstance(company, dict) else ""
        source_url = _text(job.get("redirect_url"))
        description = _text(job.get("description"))
        if not all((job_id, title, company_name, source_url, description)):
            raise ValueError("Adzuna jobs require id, title, company.display_name, redirect_url, and description")
        location = job.get("location")
        location_name = _text(location.get("display_name")) if isinstance(location, dict) else ""
        category = job.get("category")
        requirements = (_text(category.get("label")),) if isinstance(category, dict) and _text(category.get("label")) else ()
        return NormalizedPosting(
            source_name=self.name,
            source_job_id=job_id,
            title=title,
            company=company_name,
            source_url=source_url,
            description=description,
            location=location_name or None,
            employment_type=_text(job.get("contract_type")) or None,
            posted_at=_date(job.get("created")),
            requirements=requirements,
            raw_reference=json.dumps(job, sort_keys=True),
        )
