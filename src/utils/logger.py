"""Structured logging helpers built on top of structlog."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from src.config import LOG_FILE, LOG_LEVEL, VERBOSE_LOGGING

BoundLogger = structlog.stdlib.BoundLogger

_configured = False


def _coerce_level(level_name: str) -> int:
    """Translate a string/int environment value into a logging level."""
    if level_name.isdigit():
        return int(level_name)
    return getattr(logging, level_name.upper(), logging.INFO)


def _configure_logging() -> None:
    """Configure structlog with console + JSONL file outputs."""
    global _configured
    if _configured:
        return

    effective_level = logging.DEBUG if VERBOSE_LOGGING else _coerce_level(LOG_LEVEL)
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
    ]

    console_handler = logging.StreamHandler()
    console_handler.setLevel(effective_level)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=pre_chain,
        )
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(effective_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    logging.captureWarnings(True)

    # Suppress noisy Azure/HTTP loggers (request/response at INFO floods terminal during device-code polling)
    for name in (
        "azure",
        "azure.identity",
        "azure.core",
        "msrest",
        "httpx",
        "httpcore",
        "urllib3",
        "msgraph",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(effective_level),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str = "email_automation", **bindings: Any) -> BoundLogger:
    """Return the structured logger, optionally bound with context."""
    if not _configured:
        _configure_logging()
    logger = structlog.get_logger(name)
    if bindings:
        logger = logger.bind(**bindings)
    return logger


def bind_context(**context: Any) -> None:
    """Bind context variables to be included with every log entry."""
    structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys: str) -> None:
    """Remove bound context variables."""
    if keys:
        structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


def log_agent_step(agent_name: str, step: str, data: Any = None) -> None:
    """Log a structured agent step while preserving backwards compatibility."""
    logger = get_logger().bind(agent=agent_name, event="agent_step")
    if data is None:
        logger.info(step)
        return
    if VERBOSE_LOGGING:
        logger.debug(step, data=data)
    else:
        logger.info(step, data=data)
