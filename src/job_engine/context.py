"""Narrow, read-only context access for local model workflows."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .evidence import EvidenceChunk


class ContextAccessError(ValueError):
    """Raised when a context request is outside the read-only allowlist."""


RESOURCE_QUERIES = {
    "jobs": """
        SELECT id, title, company, location, source, source_url, description,
               first_seen_at, last_seen_at, status, fit_score
        FROM jobs
        WHERE (? IS NULL OR id = ?)
        ORDER BY fit_score DESC, id ASC
        LIMIT ?
    """,
    "drafts": """
        SELECT id, job_id, document_type, title, content, evidence_ids_json,
               model, model_version, gate_passed, created_at
        FROM drafts
        WHERE gate_passed = 1 AND (? IS NULL OR job_id = ?)
        ORDER BY id DESC
        LIMIT ?
    """,
    "email_status": """
        SELECT message_id, thread_id, received_at, sender, subject, category, ingested_at
        FROM email_status_messages
        WHERE (? IS NULL OR message_id = ?)
        ORDER BY received_at DESC, message_id ASC
        LIMIT ?
    """,
}


class ReadOnlyContext:
    """Expose approved context without write or policy-control operations."""

    def __init__(
        self,
        database_path: Path,
        *,
        resume_evidence: Iterable[EvidenceChunk] = (),
        repository_evidence: Iterable[EvidenceChunk] = (),
    ) -> None:
        self.database_path = database_path.expanduser().resolve()
        self._resume_evidence = tuple(resume_evidence)
        self._repository_evidence = tuple(repository_evidence)

    def read(
        self,
        resource: str,
        *,
        identifier: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Read one allowlisted resource with a bounded result set."""
        if resource in {"resume_evidence", "repository_evidence"}:
            chunks = (
                self._resume_evidence
                if resource == "resume_evidence"
                else self._repository_evidence
            )
            selected = [
                asdict(chunk)
                for chunk in chunks
                if identifier is None or chunk.chunk_id == identifier
            ]
            return selected[: self._validate_limit(limit)]
        query = RESOURCE_QUERIES.get(resource)
        if query is None:
            raise ContextAccessError(f"unsupported context resource: {resource}")
        bounded_limit = self._validate_limit(limit)
        if not self.database_path.is_file():
            raise ContextAccessError(f"context database does not exist: {self.database_path}")
        try:
            uri = f"file:{self.database_path}?mode=ro"
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    query, (identifier, identifier, bounded_limit)
                ).fetchall()
        except sqlite3.Error as exc:
            raise ContextAccessError(f"context read failed for {resource}: {exc}") from exc
        return [self._row_as_dict(resource, row) for row in rows]

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ContextAccessError("context limit must be an integer from 1 to 100")
        return limit

    @staticmethod
    def _row_as_dict(resource: str, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        if resource == "drafts":
            try:
                result["evidence_ids"] = json.loads(result.pop("evidence_ids_json"))
            except (TypeError, json.JSONDecodeError) as exc:
                raise ContextAccessError("draft contains invalid evidence references") from exc
            result["gate_passed"] = bool(result["gate_passed"])
        return result
