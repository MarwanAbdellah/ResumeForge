"""Sanitized pipeline event collection for logs and diagnostics."""

import logging
import threading
from contextlib import contextmanager
from collections import defaultdict, deque
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from .context import current_context


logger = logging.getLogger("resumeforge.pipeline")
_events: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=200))
_lock = threading.Lock()


def emit_event(stage: str, status: str, **fields) -> dict:
    context = current_context()
    event = {
        "event_id": f"evt_{uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": context.request_id,
        "session_id": context.session_id,
        "generation_id": context.generation_id,
        "stage_id": context.stage_id,
        "stage": stage,
        "status": status,
        **{key: value for key, value in fields.items() if value is not None},
    }
    logger.info("pipeline_event", extra={"observability": event})
    if context.generation_id:
        with _lock:
            _events[context.generation_id].append(event)
    return event


def get_events(generation_id: str) -> list[dict]:
    with _lock:
        return list(_events.get(generation_id, ()))


def elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)


@contextmanager
def stage_span(stage: str, **fields):
    context = current_context()
    previous = context.stage_id
    context.stage_id = f"stage_{uuid4().hex[:12]}"
    started = perf_counter()
    emit_event(stage, "started", **fields)
    try:
        yield context.stage_id
    except Exception as exc:
        duration = elapsed_ms(started)
        emit_event(stage, "failed", duration_ms=duration, exception=type(exc).__name__)
        raise
    else:
        duration = elapsed_ms(started)
        emit_event(stage, "completed", duration_ms=duration)
    finally:
        context.stage_id = previous
