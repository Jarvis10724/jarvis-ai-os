"""
Structured logging setup.

Uses structlog so every log line is a machine-parseable event with
consistent fields (timestamp, level, logger, event, plus any bound context
like user_id or plugin name). In development, logs render as readable
console output; in production they render as JSON for log aggregators.
"""
import logging
import os
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        level=settings.LOG_LEVEL,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOG_FILE),
        ],
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "jarvis") -> structlog.BoundLogger:
    return structlog.get_logger(name)
