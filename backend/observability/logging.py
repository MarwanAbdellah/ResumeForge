"""Safe structured logging configuration."""

import json
import logging
import sys
from datetime import datetime, timezone

from .context import current_context


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = current_context()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": context.request_id,
            "session_id": context.session_id,
            "generation_id": context.generation_id,
            "stage_id": context.stage_id,
        }
        if hasattr(record, "observability"):
            payload.update(record.observability)
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
