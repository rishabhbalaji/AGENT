"""Fail-closed client for a Tailscale-reachable Ollama service."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when Ollama is unavailable or returns an unsafe response."""


@dataclass(frozen=True)
class OllamaConfig:
    """Connection settings for one explicitly selected Ollama model."""

    base_url: str
    model: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if not self.model.strip():
            raise ValueError("model must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


@dataclass(frozen=True)
class OllamaModel:
    """The model identity returned by Ollama's model catalogue."""

    name: str
    digest: str
    modified_at: str


@dataclass(frozen=True)
class OllamaHealth:
    """A successful health check for the configured model."""

    endpoint: str
    model: OllamaModel


class OllamaClient:
    """Small JSON client with no model fallback or external side effects."""

    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def list_models(self) -> tuple[OllamaModel, ...]:
        document = self._request("GET", "/api/tags")
        models = document.get("models")
        if not isinstance(models, list):
            raise OllamaError("Ollama model response is missing a models list")
        parsed: list[OllamaModel] = []
        for model in models:
            if not isinstance(model, dict):
                raise OllamaError("Ollama model response contains an invalid entry")
            name = model.get("name")
            digest = model.get("digest")
            modified_at = model.get("modified_at")
            if not all(isinstance(value, str) and value.strip() for value in (name, digest, modified_at)):
                raise OllamaError("Ollama model response contains incomplete model metadata")
            parsed.append(OllamaModel(name=name, digest=digest, modified_at=modified_at))
        return tuple(parsed)

    def check_health(self) -> OllamaHealth:
        """Verify the endpoint and exact configured model without fallback."""
        models = self.list_models()
        for model in models:
            if model.name == self.config.model:
                return OllamaHealth(endpoint=self.config.normalized_base_url, model=model)
        raise OllamaError(f"configured Ollama model is unavailable: {self.config.model}")

    def generate_json(self, prompt: str) -> str:
        """Request one non-streaming JSON response from the configured model."""
        if not prompt.strip():
            raise ValueError("prompt must be non-empty")
        document = self._request(
            "POST",
            "/api/chat",
            {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
            },
        )
        message = document.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaError("Ollama response is missing message content")
        content = message["content"].strip()
        if not content:
            raise OllamaError("Ollama returned an empty response")
        return content

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.config.normalized_base_url}{path}",
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raise OllamaError(f"Ollama request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("Ollama response was not valid JSON") from exc
        if not isinstance(document, dict):
            raise OllamaError("Ollama response must be a JSON object")
        return document
