"""Structured logging (structlog → JSON). Blueprint §H.1. Phase 9 ships OTEL/Loki shipping."""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger().bind(component=component)
