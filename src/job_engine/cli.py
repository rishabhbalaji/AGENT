"""Command-line entry point for the local job application engine."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
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
    discovery.add_argument("--board", action="append", required=True)
    discovery.add_argument("--timeout", type=float, default=15.0)
    discovery.add_argument(
        "--persist",
        action="store_true",
        help="write results to SQLite; without this flag the command is a dry run",
    )
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
            reports = []
            for board in args.board:
                report = discover(
                    GreenhouseAdapter(board, source_name=f"greenhouse:{board}", timeout=args.timeout),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
