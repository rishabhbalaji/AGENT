"""Minimal server-rendered review dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import ipaddress

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


QUEUE_NAMES = ("applied", "apply-yourself", "parked", "drafts")
TAILSCALE_NETWORK = ipaddress.ip_network("100.64.0.0/10")


class DashboardBindingError(ValueError):
    """Raised when a dashboard bind address is not locally restricted."""


@dataclass(frozen=True)
class QueueItem:
    """One review item displayed by the dashboard."""

    job_id: str
    title: str
    company: str
    summary: str


def validate_bind_host(host: str) -> str:
    """Allow loopback or Tailscale addresses, never wildcard/public binds."""
    candidate = host.strip()
    if not candidate:
        raise DashboardBindingError("dashboard host must be non-empty")
    if candidate in {"localhost", "127.0.0.1", "::1"}:
        return candidate
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise DashboardBindingError(
            "dashboard host must be loopback or a Tailscale 100.64.0.0/10 address"
        ) from exc
    if address.version != 4 or address not in TAILSCALE_NETWORK:
        raise DashboardBindingError(
            "dashboard host must be loopback or a Tailscale 100.64.0.0/10 address"
        )
    return candidate


def _queue_items(
    queues: dict[str, tuple[QueueItem, ...]],
    queue_name: str,
) -> tuple[QueueItem, ...]:
    return queues.get(queue_name, ())


def create_dashboard_app(
    queues: dict[str, tuple[QueueItem, ...]] | None = None,
) -> FastAPI:
    """Create a dashboard app with an isolated, read-only queue snapshot."""
    queue_data = dict(queues or {})
    app = FastAPI(title="Local Job Application Engine")

    @app.get("/health", response_class=HTMLResponse)
    def health() -> str:
        return "<html><body><h1>Dashboard healthy</h1></body></html>"

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        links = " ".join(
            f'<a href="/queue/{escape(name)}">{escape(name)}</a>'
            for name in QUEUE_NAMES
        )
        return (
            "<html><body><h1>Job review dashboard</h1>"
            f"<nav>{links}</nav>"
            "<p>Review only. This dashboard does not submit applications.</p>"
            "</body></html>"
        )

    @app.get("/queue/{queue_name}", response_class=HTMLResponse)
    def queue(queue_name: str) -> str:
        if queue_name not in QUEUE_NAMES:
            return HTMLResponse("<h1>Queue not found</h1>", status_code=404)
        items = _queue_items(queue_data, queue_name)
        rendered = "".join(
            (
                "<li>"
                f"<strong>{escape(item.title)}</strong> — {escape(item.company)}"
                f"<p>{escape(item.summary)}</p>"
                f"<small>{escape(item.job_id)}</small>"
                "</li>"
            )
            for item in items
        )
        return (
            "<html><body>"
            f"<h1>{escape(queue_name)} queue</h1>"
            '<p><a href="/">All queues</a></p>'
            f"<ul>{rendered or '<li>No items</li>'}</ul>"
            "</body></html>"
        )

    return app


def empty_queues() -> dict[str, tuple[QueueItem, ...]]:
    """Return the stable empty queue shape used before persistence wiring."""
    return {name: () for name in QUEUE_NAMES}
