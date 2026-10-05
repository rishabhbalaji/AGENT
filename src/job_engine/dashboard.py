"""Server-rendered review dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import ipaddress
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .database import DatabaseError, migrate


QUEUE_NAMES = ("applied", "apply-yourself", "parked", "drafts")
QUEUE_LABELS = {
    "applied": ("Applied", "Completed applications", "green"),
    "apply-yourself": ("Apply yourself", "Needs your review", "amber"),
    "parked": ("Parked", "Set aside for later", "slate"),
    "drafts": ("Drafts", "Material ready to inspect", "blue"),
}
TAILSCALE_NETWORK = ipaddress.ip_network("100.64.0.0/10")
QUEUE_STATUSES = {
    "applied": ("applied",),
    "apply-yourself": ("apply_yourself", "shortlisted"),
    "parked": ("parked", "rejected"),
    "drafts": ("drafted",),
}
APPLICATION_QUEUE_FILTERS = {
    "applied": ("status IN (?, ?)", ("submitted", "applied")),
    "apply-yourself": ("route = ?", ("review",)),
    "parked": ("route = ?", ("park",)),
    "drafts": ("route = ? OR status = ?", ("draft_for_approval", "drafted")),
}


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


def _layout(content: str, *, title: str, active_queue: str | None = None) -> str:
    navigation = "".join(
        (
            f'<a class="nav-item {"active" if name == active_queue else ""}" '
            f'href="/queue/{escape(name)}">'
            f'<span>{escape(QUEUE_LABELS[name][0])}</span>'
            f'<span class="nav-slug">{escape(name)}</span>'
            "</a>"
        )
        for name in QUEUE_NAMES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · Job Engine</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0c111c;
      --panel: #121a2a;
      --panel-strong: #172238;
      --line: #26344d;
      --text: #edf3ff;
      --muted: #91a0bb;
      --accent: #79a8ff;
      --green: #55d6a3;
      --amber: #f5c76b;
      --blue: #79a8ff;
      --slate: #9aa8be;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at 15% 0%, #172641 0, var(--bg) 42rem);
      color: var(--text);
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ display: flex; min-height: 100vh; }}
    aside {{
      width: 250px; flex: 0 0 250px; padding: 28px 18px;
      border-right: 1px solid var(--line); background: rgba(12, 17, 28, .82);
    }}
    .brand {{ display: flex; gap: 11px; align-items: center; margin: 0 10px 40px; }}
    .brand-mark {{
      display: grid; place-items: center; width: 34px; height: 34px;
      border-radius: 10px; color: #07101e; background: var(--accent); font-weight: 900;
    }}
    .brand strong {{ display: block; font-size: 15px; letter-spacing: .01em; }}
    .brand small {{ color: var(--muted); font-size: 11px; }}
    .eyebrow {{ color: var(--muted); font-size: 11px; letter-spacing: .13em; text-transform: uppercase; }}
    .nav {{ display: grid; gap: 7px; margin-top: 12px; }}
    .nav-item {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 11px 12px; border: 1px solid transparent; border-radius: 10px; color: var(--muted);
    }}
    .nav-item:hover, .nav-item.active {{ border-color: var(--line); background: var(--panel); color: var(--text); }}
    .nav-item.active {{ box-shadow: inset 3px 0 var(--accent); }}
    .nav-slug {{ font-size: 11px; opacity: .62; }}
    main {{ width: min(1120px, 100%); padding: 40px clamp(22px, 5vw, 68px); }}
    .topbar {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 34px; }}
    h1 {{ margin: 5px 0 7px; font-size: clamp(28px, 4vw, 42px); letter-spacing: -.04em; line-height: 1.05; }}
    .subtle {{ margin: 0; color: var(--muted); max-width: 620px; }}
    .notice {{
      max-width: 250px; padding: 12px 14px; border: 1px solid #315178;
      border-radius: 12px; background: rgba(33, 64, 105, .28); color: #bdd7ff; font-size: 12px;
    }}
    .notice strong {{ display: block; margin-bottom: 2px; color: var(--text); font-size: 13px; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px; }}
    .stat {{ padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: rgba(18, 26, 42, .72); }}
    .stat .number {{ display: block; margin-top: 4px; font-size: 27px; font-weight: 750; }}
    .stat .label {{ color: var(--muted); font-size: 12px; }}
    .section-head {{ display: flex; align-items: end; justify-content: space-between; margin-bottom: 14px; }}
    .section-head h2 {{ margin: 0; font-size: 20px; letter-spacing: -.02em; }}
    .section-head span {{ color: var(--muted); font-size: 12px; }}
    .cards {{ display: grid; gap: 12px; }}
    .card {{
      display: grid; grid-template-columns: 1fr auto; gap: 20px; padding: 19px 20px;
      border: 1px solid var(--line); border-radius: 13px; background: rgba(18, 26, 42, .82);
    }}
    .card:hover {{ border-color: #3c5882; background: var(--panel-strong); }}
    .card h3 {{ margin: 0 0 4px; font-size: 17px; }}
    .company {{ color: var(--accent); font-size: 13px; }}
    .summary {{ margin: 12px 0 0; color: var(--muted); font-size: 13px; }}
    .job-id {{ align-self: start; color: #71809a; font: 11px ui-monospace, SFMono-Regular, monospace; }}
    .empty {{ padding: 42px 20px; border: 1px dashed #33435f; border-radius: 13px; text-align: center; background: rgba(18, 26, 42, .42); }}
    .empty strong {{ display: block; margin-bottom: 5px; font-size: 16px; }}
    .empty span {{ color: var(--muted); font-size: 13px; }}
    footer {{ margin-top: 42px; color: #66758f; font-size: 11px; }}
    @media (max-width: 760px) {{
      .shell {{ display: block; }}
      aside {{ width: 100%; padding: 18px; border-right: 0; border-bottom: 1px solid var(--line); }}
      .brand {{ margin-bottom: 20px; }}
      .nav {{ grid-template-columns: repeat(2, 1fr); }}
      main {{ padding: 30px 18px; }}
      .topbar {{ display: block; }}
      .notice {{ max-width: none; margin-top: 20px; }}
      .stats {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 430px) {{ .stats {{ grid-template-columns: 1fr 1fr; }} .card {{ display: block; }} .job-id {{ display: block; margin-top: 14px; }} }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <a class="brand" href="/">
        <span class="brand-mark">J</span>
        <span><strong>Job Engine</strong><small>local review desk</small></span>
      </a>
      <div class="eyebrow">Workspace</div>
      <nav class="nav" aria-label="Review queues">{navigation}</nav>
    </aside>
    <main>{content}<footer>Read-only workspace · applications are never submitted from this dashboard.</footer></main>
  </div>
</body>
</html>"""


def queues_from_database(database_path: Path) -> dict[str, tuple[QueueItem, ...]]:
    """Load read-only review queues from the persisted jobs table."""
    database_path = database_path.expanduser()
    migrate(database_path)
    queues = {name: [] for name in QUEUE_NAMES}
    try:
        with sqlite3.connect(database_path) as connection:
            for queue_name, statuses in QUEUE_STATUSES.items():
                placeholders = ",".join("?" for _ in statuses)
                application_filter, application_values = APPLICATION_QUEUE_FILTERS[queue_name]
                rows = connection.execute(
                    f"""
                    SELECT id, title, company, COALESCE(description, '')
                    FROM jobs
                    WHERE status IN ({placeholders})
                       OR EXISTS (
                           SELECT 1
                           FROM applications
                           WHERE applications.job_id = jobs.id
                             AND ({application_filter})
                       )
                    ORDER BY last_seen_at DESC, id ASC
                    """,
                    (*statuses, *application_values),
                )
                queues[queue_name].extend(
                    QueueItem(
                        job_id=str(job_id),
                        title=str(title),
                        company=str(company),
                        summary=str(description),
                    )
                    for job_id, title, company, description in rows
                )
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot load dashboard queues from {database_path}: {exc}") from exc
    return {name: tuple(items) for name, items in queues.items()}


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
        stats = "".join(
            (
                '<div class="stat">'
                f'<span class="eyebrow">{escape(QUEUE_LABELS[name][0])}</span>'
                f'<span class="number">{len(_queue_items(queue_data, name))}</span>'
                f'<span class="label">{escape(QUEUE_LABELS[name][1])}</span>'
                "</div>"
            )
            for name in QUEUE_NAMES
        )
        return _layout(
            (
                '<div class="topbar"><div><div class="eyebrow">Daily review</div>'
                "<h1>Keep the pipeline moving.</h1>"
                '<p class="subtle">A calm, local workspace for deciding what deserves your attention next.</p>'
                '</div><div class="notice"><strong>Review only</strong>'
                "This dashboard does not submit applications.</div></div>"
                f'<section class="stats" aria-label="Queue summary">{stats}</section>'
                '<div class="section-head"><h2>Queue overview</h2>'
                "<span>Choose a queue to inspect its items</span></div>"
                '<div class="cards">'
                + "".join(
                    (
                        f'<a class="card" href="/queue/{escape(name)}">'
                        f"<div><h3>{escape(QUEUE_LABELS[name][0])}</h3>"
                        f'<span class="company">{escape(QUEUE_LABELS[name][1])}</span></div>'
                        f'<span class="job-id">{len(_queue_items(queue_data, name))} items</span></a>'
                    )
                    for name in QUEUE_NAMES
                )
                + "</div>"
            ),
            title="Daily review",
        )

    @app.get("/queue/{queue_name}", response_class=HTMLResponse)
    def queue(queue_name: str) -> str:
        if queue_name not in QUEUE_NAMES:
            return HTMLResponse("<h1>Queue not found</h1>", status_code=404)
        items = _queue_items(queue_data, queue_name)
        rendered = "".join(
            (
                '<article class="card">'
                f"<div><h3>{escape(item.title)}</h3>"
                f'<span class="company">{escape(item.company)}</span>'
                f'<p class="summary">{escape(item.summary) or "No summary available."}</p></div>'
                f'<span class="job-id">{escape(item.job_id)}</span>'
                "</article>"
            )
            for item in items
        )
        empty = (
            '<div class="empty"><strong>Nothing here yet</strong>'
            f'<span>{escape(QUEUE_LABELS[queue_name][1])} will appear in this queue.</span></div>'
        )
        return _layout(
            (
                f'<div class="topbar"><div><div class="eyebrow">Review queue</div>'
                f"<h1>{escape(QUEUE_LABELS[queue_name][0])}</h1>"
                f'<p class="subtle">{escape(QUEUE_LABELS[queue_name][1])}.</p></div>'
                f'<div class="notice"><strong>{len(items)} items</strong>'
                "Read-only review; no automatic submissions.</div></div>"
                f'<div class="section-head"><h2>Items</h2><span>{len(items)} total</span></div>'
                f'<div class="cards">{rendered or empty}</div>'
            ),
            title=QUEUE_LABELS[queue_name][0],
            active_queue=queue_name,
        )

    return app


def empty_queues() -> dict[str, tuple[QueueItem, ...]]:
    """Return the stable empty queue shape used before persistence wiring."""
    return {name: () for name in QUEUE_NAMES}
