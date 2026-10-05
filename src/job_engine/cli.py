"""Command-line entry point for the local job application engine."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import ConfigurationError
from .database import DatabaseError
from .dashboard import DashboardBindingError, validate_bind_host
from .health import run_health_from_strings
from .logging import configure_logging
from .storage_check import StorageCheckError


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
