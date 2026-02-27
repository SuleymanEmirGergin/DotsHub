"""Structured logging: JSON format with request_id when LOG_FORMAT=json."""

import json
import logging
import os
from datetime import datetime, timezone

from app.core.request_id import get_request_id


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            log_dict["request_id"] = rid
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_dict, ensure_ascii=False)


def setup_logging() -> None:
    """Configure root logger: JSON when LOG_FORMAT=json, else default."""
    log_format = os.environ.get("LOG_FORMAT", "").strip().lower()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if log_format == "json":
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        root.addHandler(handler)
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level, logging.INFO))
