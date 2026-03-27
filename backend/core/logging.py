"""Structured logging configuration.

Provides JSON and text formatters with a single ``setup_logging`` entry
point that should be called once at application startup.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line on stderr."""

    # Fields from LogRecord that we never want in the JSON output.
    # Includes all standard LogRecord attributes to prevent KeyError when
    # caller-supplied extra keys accidentally shadow them.
    _SKIP_FIELDS: frozenset[str] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge caller-supplied extra fields.
        for key, value in record.__dict__.items():
            if key in self._SKIP_FIELDS or key in payload:
                continue
            # Skip private / internal attributes.
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)  # serialisability check
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)

        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


_TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure the root logger.

    Args:
        log_level: Any standard level name (DEBUG, INFO, WARNING, …).
        log_format: ``"json"`` for structured output, anything else for
            human-readable text lines.
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Suppress noisy third-party loggers.
    for name in ("httpx", "httpcore", "openai", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
