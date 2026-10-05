"""Deterministic, provenance-preserving evidence chunk retrieval."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

from .github_index import RepositoryIndex
from .resume import ResumeDocument


PayloadFetcher = Callable[[str], dict[str, Any]]
TEXT_SUFFIXES = frozenset(
    {".md", ".txt", ".rst", ".py", ".js", ".ts", ".java", ".go", ".rs", ".json", ".yaml", ".yml"}
)


class EvidenceRetrievalError(ValueError):
    """Raised when source evidence cannot be decoded safely."""


@dataclass(frozen=True)
class EvidenceChunk:
    """One deterministic evidence chunk with a stable source reference."""

    chunk_id: str
    source_type: str
    source_ref: str
    ordinal: int
    content: str
    content_sha256: str


def _chunks(text: str, *, source_type: str, source_ref: str, chunk_size: int) -> tuple[EvidenceChunk, ...]:
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return ()
    chunks: list[EvidenceChunk] = []
    for ordinal, start in enumerate(range(0, len(normalized), chunk_size)):
        content = normalized[start : start + chunk_size].strip()
        if not content:
            continue
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        identity = f"{source_type}:{source_ref}:{ordinal}:{content_hash}"
        chunks.append(
            EvidenceChunk(
                chunk_id=sha256(identity.encode("utf-8")).hexdigest(),
                source_type=source_type,
                source_ref=source_ref,
                ordinal=ordinal,
                content=content,
                content_sha256=content_hash,
            )
        )
    return tuple(chunks)


def resume_evidence(
    resume: ResumeDocument,
    *,
    chunk_size: int = 1200,
) -> tuple[EvidenceChunk, ...]:
    """Chunk extracted resume text while retaining its source hash as provenance."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    return _chunks(
        resume.text,
        source_type="resume",
        source_ref=f"{resume.source_path}#sha256={resume.sha256}",
        chunk_size=chunk_size,
    )


def _is_text_file(path: str) -> bool:
    return any(path.casefold().endswith(suffix) for suffix in TEXT_SUFFIXES)


def _decode_blob(payload: dict[str, Any], source_ref: str) -> str:
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise EvidenceRetrievalError(f"GitHub blob is not base64 content: {source_ref}")
    try:
        return base64.b64decode(payload["content"], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise EvidenceRetrievalError(f"GitHub blob is not UTF-8 text: {source_ref}") from exc


def repository_evidence(
    index: RepositoryIndex,
    *,
    fetcher: PayloadFetcher,
    chunk_size: int = 1200,
) -> tuple[EvidenceChunk, ...]:
    """Retrieve chunks only for text files already present in a repository index."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    chunks: list[EvidenceChunk] = []
    for file in index.files:
        if not _is_text_file(file.path):
            continue
        content = _decode_blob(fetcher(file.url), file.url)
        chunks.extend(
            _chunks(
                content,
                source_type="github",
                source_ref=f"{index.repository_url}@{index.default_branch}:{file.path}#sha={file.sha}",
                chunk_size=chunk_size,
            )
        )
    return tuple(chunks)
