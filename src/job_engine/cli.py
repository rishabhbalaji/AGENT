"""Command-line entry point for the local job application engine."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from . import __version__
from .config import ConfigurationError, load_config
from .database import DatabaseError
from .dashboard import DashboardBindingError, validate_bind_host
from .health import run_health_from_strings
from .logging import configure_logging
from .ollama import OllamaClient, OllamaConfig, OllamaError
from .ollama_benchmark import benchmark_models, results_as_json
from .storage_check import StorageCheckError
from .fixtures import FixtureError, seed_fixture_database
from .discovery import discover
from .greenhouse import GreenhouseAdapter
from .public_feed import GovUkFindAJobAdapter
from .worker import clear_pause, pause_status, run_discovery_worker, set_pause
from .backups import backup_database, prune_backups
from .recovery import run_recovery_checks
from .gmail_ingestion import (
    GmailIngestionError,
    authorize_gmail,
    build_gmail_service,
    list_status_messages,
    persist_status_messages,
)
from .agent_corner import AgentCornerIsolationError, AgentCornerPaths, prepare_paths
from .context import ContextAccessError, ReadOnlyContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-engine",
        description="Local-first job discovery and application assistant.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )
    subparsers = parser.add_subparsers(dest="command")
    health = subparsers.add_parser(
        "health",
        help="validate local prerequisites and record a dry-run health event",
    )
    health.add_argument("--config-dir", type=Path, default=Path("config/examples"))
    health.add_argument("--data-root", type=Path, required=True)
    health.add_argument("--database", type=Path)
    health.add_argument(
        "--at",
        help="ISO-8601 instant to evaluate instead of the current time",
    )
    health.add_argument(
        "--paused",
        action="store_true",
        help="resolve the health check while the engine is paused",
    )
    dashboard = subparsers.add_parser(
        "dashboard",
        help="run the local review dashboard",
    )
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8000)
    dashboard.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    demo = subparsers.add_parser(
        "demo-data",
        help="seed fictional offline postings into a local database for review",
    )
    demo.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    demo.add_argument("--fixtures-dir", type=Path, default=Path("fixtures"))
    ollama = subparsers.add_parser(
        "ollama-health",
        help="verify the configured Ollama endpoint and exact model",
    )
    ollama.add_argument("--endpoint", required=True)
    ollama.add_argument("--model", required=True)
    ollama.add_argument("--timeout", type=float, default=10.0)
    benchmark = subparsers.add_parser(
        "ollama-benchmark",
        help="benchmark configured Ollama models against fictional fixtures",
    )
    benchmark.add_argument("--endpoint", required=True)
    benchmark.add_argument("--model", action="append", required=True)
    benchmark.add_argument("--timeout", type=float, default=60.0)
    benchmark.add_argument("--output", type=Path)
    discovery = subparsers.add_parser(
        "discover",
        help="fetch configured public Greenhouse boards and evaluate profiles",
    )
    discovery.add_argument("--config-dir", type=Path, default=Path("config/local"))
    discovery.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    discovery.add_argument(
        "--board",
        action="append",
        default=[],
        help="Greenhouse board slug; may be repeated",
    )
    discovery.add_argument(
        "--govuk-endpoint",
        help="explicit public GOV.UK Find a Job JSON endpoint",
    )
    discovery.add_argument("--timeout", type=float, default=15.0)
    discovery.add_argument(
        "--persist",
        action="store_true",
        help="write results to SQLite; without this flag the command is a dry run",
    )
    worker = subparsers.add_parser(
        "discover-worker",
        help="run one persistent, lock-protected public discovery pass",
    )
    worker.add_argument("--config-dir", type=Path, default=Path("config/local"))
    worker.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    worker.add_argument(
        "--board",
        action="append",
        default=[],
        help="Greenhouse board slug; may be repeated",
    )
    worker.add_argument(
        "--govuk-endpoint",
        help="explicit public GOV.UK Find a Job JSON endpoint",
    )
    worker.add_argument("--timeout", type=float, default=20.0)
    worker.add_argument("--lock-file", type=Path, default=Path("engine.discovery.lock"))
    worker.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    pause = subparsers.add_parser(
        "pause",
        help="pause supervised workers by creating a control marker",
    )
    pause.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    resume = subparsers.add_parser(
        "resume",
        help="resume supervised workers by removing a control marker",
    )
    resume.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    worker_status = subparsers.add_parser(
        "worker-status",
        help="show whether supervised workers are paused",
    )
    worker_status.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    backup = subparsers.add_parser(
        "backup",
        help="create and verify a local SQLite backup",
    )
    backup.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    backup.add_argument("--backup-root", type=Path, required=True)
    backup.add_argument("--keep", type=int, default=0)
    recovery = subparsers.add_parser(
        "recovery-check",
        help="run read-only database, backup, and worker recovery checks",
    )
    recovery.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    recovery.add_argument("--backup-root", type=Path, default=Path("backups"))
    recovery.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    gmail = subparsers.add_parser(
        "gmail-status",
        help="poll recent Gmail status messages using read-only OAuth",
    )
    gmail.add_argument("--client-secret", type=Path, required=True)
    gmail.add_argument("--token", type=Path, required=True)
    gmail.add_argument("--database", type=Path, default=Path("engine.sqlite3"))
    gmail.add_argument("--lookback-hours", type=float, default=72.0)
    gmail.add_argument("--max-messages", type=int, default=100)
    gmail.add_argument("--query", default="in:anywhere")
    gmail.add_argument("--pause-file", type=Path, default=Path("PAUSED"))
    corner = subparsers.add_parser(
        "agent-corner-check",
        help="validate and prepare isolated Agent Corner paths",
    )
    corner.add_argument("--root", type=Path, required=True)
    corner.add_argument("--production-root", type=Path, required=True)
    context = subparsers.add_parser(
        "context",
        help="read an allowlisted context resource without mutation access",
    )
    context.add_argument("--database", type=Path, required=True)
    context.add_argument(
        "--resource",
        choices=("jobs", "drafts", "email_status", "resume_evidence", "repository_evidence"),
        required=True,
    )
    context.add_argument("--id", dest="identifier")
    context.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level)
    if args.command == "health":
        try:
            result = run_health_from_strings(
                config_dir=args.config_dir,
                data_root=args.data_root,
                database_path=args.database,
                at=args.at,
                paused=args.paused,
            )
        except (ConfigurationError, DatabaseError, StorageCheckError, ValueError) as exc:
            print(f"health check failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "demo-data":
        try:
            inserted = seed_fixture_database(args.database, args.fixtures_dir)
        except (DatabaseError, FixtureError, ValueError) as exc:
            print(f"demo data failed: {exc}", file=sys.stderr)
            return 1
        print(f"Seeded {inserted} fictional postings into {args.database}")
    elif args.command == "dashboard":
        try:
            import uvicorn

            from .dashboard import create_dashboard_app, queues_from_database

            host = validate_bind_host(args.host)
            print(f"Dashboard available at http://{host}:{args.port}", flush=True)
            uvicorn.run(
                create_dashboard_app(
                    queues_from_database(args.database),
                    database_path=args.database,
                ),
                host=host,
                port=args.port,
            )
        except (DashboardBindingError, DatabaseError, ValueError) as exc:
            print(f"dashboard failed: {exc}", file=sys.stderr)
            return 1
        except ImportError as exc:
            print(f"dashboard failed: missing dependency: {exc}", file=sys.stderr)
            return 1
    elif args.command == "ollama-health":
        try:
            health = OllamaClient(
                OllamaConfig(
                    base_url=args.endpoint,
                    model=args.model,
                    timeout_seconds=args.timeout,
                )
            ).check_health()
        except (OllamaError, ValueError) as exc:
            print(f"ollama health failed: {exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "endpoint": health.endpoint,
                    "model": health.model.name,
                    "digest": health.model.digest,
                    "modified_at": health.model.modified_at,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "ollama-benchmark":
        try:
            results = benchmark_models(
                args.endpoint,
                tuple(args.model),
                timeout_seconds=args.timeout,
            )
            serialized = results_as_json(results)
            if args.output:
                args.output.write_text(serialized + "\n", encoding="utf-8")
            print(serialized)
        except (OllamaError, ValueError, OSError) as exc:
            print(f"ollama benchmark failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "discover":
        try:
            configuration = load_config(args.config_dir)
            adapters = [
                GreenhouseAdapter(
                    board,
                    source_name=f"greenhouse:{board}",
                    timeout=args.timeout,
                )
                for board in args.board
            ]
            if args.govuk_endpoint:
                adapters.append(
                    GovUkFindAJobAdapter(args.govuk_endpoint, timeout=args.timeout)
                )
            if not adapters:
                raise ValueError("provide --board or --govuk-endpoint")
            reports = []
            for adapter in adapters:
                report = discover(
                    adapter,
                    configuration,
                    database_path=args.database,
                    dry_run=not args.persist,
                )
                reports.append(
                    {
                        "source": report.source,
                        "health_status": report.health_status,
                        "records_seen": report.records_seen,
                        "persisted": report.persisted,
                        "jobs": [
                            {
                                "id": job.stable_id,
                                "title": job.title,
                                "company": job.company,
                                "status": job.status,
                                "profile": job.decision.profile_name,
                                "score": job.decision.score,
                                "reasons": list(job.decision.reasons),
                                "unknowns": list(job.decision.unknowns),
                                "url": job.source_url,
                            }
                            for job in report.jobs
                        ],
                    }
                )
            print(json.dumps(reports, indent=2, sort_keys=True))
        except (ConfigurationError, DatabaseError, ValueError, OSError) as exc:
            print(f"discovery failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "discover-worker":
        try:
            configuration = load_config(args.config_dir)
            adapters = [
                GreenhouseAdapter(
                    board,
                    source_name=f"greenhouse:{board}",
                    timeout=args.timeout,
                )
                for board in args.board
            ]
            if args.govuk_endpoint:
                adapters.append(
                    GovUkFindAJobAdapter(args.govuk_endpoint, timeout=args.timeout)
                )
            if not adapters:
                raise ValueError("provide --board or --govuk-endpoint")
            result = run_discovery_worker(
                tuple(adapters),
                configuration,
                database_path=args.database,
                lock_path=args.lock_file,
                pause_path=args.pause_file,
            )
            if result.status != "completed":
                print(json.dumps({"status": result.status}, sort_keys=True))
                return 1 if result.status == "ollama_unavailable" else 0
            report = result.value
            print(
                json.dumps(
                    {
                        "status": "completed",
                        "sources": len(report.reports),
                        "jobs": len(report.jobs),
                        "persisted": report.persisted,
                    },
                    sort_keys=True,
                )
            )
        except (ConfigurationError, DatabaseError, OllamaError, ValueError, OSError) as exc:
            print(f"discovery worker failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "pause":
        try:
            path = set_pause(args.pause_file)
            print(json.dumps({"paused": True, "pause_file": str(path)}))
        except OSError as exc:
            print(f"pause failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "resume":
        try:
            path = clear_pause(args.pause_file)
            print(json.dumps({"paused": False, "pause_file": str(path)}))
        except OSError as exc:
            print(f"resume failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "worker-status":
        print(
            json.dumps(
                {
                    "paused": pause_status(args.pause_file),
                    "pause_file": str(args.pause_file.expanduser()),
                }
            )
        )
    elif args.command == "backup":
        try:
            destination = backup_database(args.database, args.backup_root)
            removed = prune_backups(args.backup_root, keep=args.keep) if args.keep else ()
            print(
                json.dumps(
                    {
                        "backup": str(destination),
                        "integrity": "ok",
                        "removed": [str(path) for path in removed],
                    },
                    sort_keys=True,
                )
            )
        except (DatabaseError, OSError, ValueError) as exc:
            print(f"backup failed: {exc}", file=sys.stderr)
            return 1
    elif args.command == "recovery-check":
        checks = run_recovery_checks(args.database, args.backup_root, args.pause_file)
        print(
            json.dumps(
                [
                    {"name": check.name, "status": check.status, "detail": check.detail}
                    for check in checks
                ],
                indent=2,
                sort_keys=True,
            )
        )
        if any(check.status == "failed" for check in checks):
            return 1
    elif args.command == "gmail-status":
        try:
            if args.lookback_hours <= 0:
                raise ValueError("lookback-hours must be positive")
            if args.pause_file.exists():
                raise GmailIngestionError("Gmail ingestion is paused")
            credentials = authorize_gmail(args.client_secret, args.token)
            service = build_gmail_service(credentials)
            messages = list_status_messages(
                service,
                lookback=timedelta(hours=args.lookback_hours),
                max_messages=args.max_messages,
                query=args.query,
            )
            inserted = persist_status_messages(args.database, messages)
        except (GmailIngestionError, DatabaseError, ValueError) as exc:
            print(f"gmail status ingestion failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"fetched": len(messages), "inserted": inserted}, sort_keys=True))
    elif args.command == "agent-corner-check":
        try:
            paths = prepare_paths(
                AgentCornerPaths.from_root(args.root),
                production_root=args.production_root,
            )
        except (AgentCornerIsolationError, OSError) as exc:
            print(f"agent corner isolation failed: {exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "status": "ready",
                    "root": str(paths.root),
                    "data": str(paths.data),
                    "credentials": str(paths.credentials),
                    "browser": str(paths.browser),
                    "jobs": str(paths.jobs),
                },
                sort_keys=True,
            )
        )
    elif args.command == "context":
        try:
            result = ReadOnlyContext(args.database).read(
                args.resource,
                identifier=args.identifier,
                limit=args.limit,
            )
        except ContextAccessError as exc:
            print(f"context read failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
