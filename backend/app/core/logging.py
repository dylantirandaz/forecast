"""Structured logging configuration using structlog.

Call ``setup_logging()`` once at application startup (e.g. in the FastAPI
lifespan handler) to configure both structlog and the stdlib logging module
for consistent JSON output.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(
    *,
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structlog and stdlib logging for the application.

    Parameters
    ----------
    log_level:
        Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    json_output:
        When *True* (default) logs are emitted as single-line JSON objects.
        When *False* a human-friendly coloured console renderer is used
        (useful for local development).
    """
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Configure the root stdlib logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "httpcore", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger.

    Parameters
    ----------
    name:
        Logger name, typically ``__name__`` of the calling module.

    Returns
    -------
    structlog.stdlib.BoundLogger
    """
    return structlog.get_logger(name)
