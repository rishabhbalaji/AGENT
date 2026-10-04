"""Structured logging setup for the engine."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure consistent console logging for CLI and workers."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
