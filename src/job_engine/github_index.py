"""Read-only indexing for explicitly allowlisted public GitHub repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PayloadFetcher = Callable[[str], dict[str, Any]]


class GitHubIndexError(ValueError):
    """Raised when an allowlisted repository cannot be indexed safely."""


@dataclass(frozen=True)
class RepositoryFile:
    """One file entry from a public repository tree."""

    path: str
    sha: str
    size: int | None
    url: str


@dataclass(frozen=True)
class RepositoryIndex:
    """Read-only repository metadata and file inventory."""

    repository_url: str
    owner: str
    name: str
    default_branch: str
    files: tuple[RepositoryFile, ...]


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "local-job-application-engine/0.1",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise GitHubIndexError("GitHub response root must be an object")
    return payload


def _repository_parts(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != "github.com":
        raise GitHubIndexError("repository must be an HTTPS GitHub URL")
    parts = tuple(part for part in parsed.path.split("/") if part)
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise GitHubIndexError("repository URL must identify owner and repository")
    return parts[0], parts[1].removesuffix(".git")


class GitHubRepositoryIndexer:
    """Index only repositories explicitly supplied in the local allowlist."""

    def __init__(
        self,
        repositories: tuple[str, ...],
        *,
        fetcher: PayloadFetcher = _fetch_json,
    ) -> None:
        if not repositories:
            raise ValueError("at least one repository is required")
        self._repositories = tuple(repositories)
        self._fetcher = fetcher

    def index(self) -> tuple[RepositoryIndex, ...]:
        indexes: list[RepositoryIndex] = []
        for repository_url in self._repositories:
            owner, name = _repository_parts(repository_url)
            metadata_url = f"https://api.github.com/repos/{owner}/{name}"
            metadata = self._fetcher(metadata_url)
            branch = metadata.get("default_branch")
            if not isinstance(branch, str) or not branch.strip():
                raise GitHubIndexError(f"repository metadata lacks default branch: {repository_url}")
            tree_url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{branch}?recursive=1"
            tree = self._fetcher(tree_url)
            entries = tree.get("tree")
            if not isinstance(entries, list):
                raise GitHubIndexError(f"repository tree is malformed: {repository_url}")
            files = tuple(
                RepositoryFile(
                    path=entry["path"],
                    sha=entry["sha"],
                    size=entry.get("size") if isinstance(entry.get("size"), int) else None,
                    url=entry["url"],
                )
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("type") == "blob"
                and isinstance(entry.get("path"), str)
                and isinstance(entry.get("sha"), str)
                and isinstance(entry.get("url"), str)
            )
            indexes.append(
                RepositoryIndex(
                    repository_url=repository_url,
                    owner=owner,
                    name=name,
                    default_branch=branch,
                    files=files,
                )
            )
        return tuple(indexes)
