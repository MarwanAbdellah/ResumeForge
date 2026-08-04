"""Pipeline event emission and stage span helpers.

Keeps the historic :func:`emit_event` / :func:`stage_span` / :func:`get_events`
API but routes everything through the central :class:`PipelineEventBus` (see
:mod:`observability.bus`). ``stage_span`` binds a fresh child context instead of
mutating the shared one, so concurrent spans running in threads are isolated.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from time import perf_counter

from config.settings import settings
from .bus import PipelineEvent, bus
from .context import bind_context, current_context, reset_context
from .sinks import BufferSink, JsonLogSink, MetricsSink, CLILineSink
from .metrics import metrics

logger = logging.getLogger("resumeforge.pipeline")

_TYPED = {
    "duration_ms", "retry_count", "validation_status",
    "prompt_tokens", "completion_tokens", "total_tokens",
    "estimated_cost_usd", "error", "started_at", "ended_at",
}


class Events:
    """Thin façade over the global bus with a dedicated in-memory buffer."""

    def __init__(self) -> None:
        self._buffer = BufferSink(capacity=settings.event_buffer_capacity,
                                  max_pipelines=10_000)
        bus.subscribe(self._buffer)
        bus.subscribe(JsonLogSink())
        bus.subscribe(MetricsSink(metrics))
        if settings.cli_timeline:
            bus.subscribe(CLILineSink())


_events = Events()


def emit_event(stage: str, status: str, **fields) -> dict:
    context = current_context()
    typed = {k: fields.pop(k, None) for k in _TYPED}
    warnings = fields.pop("warnings", None)
    event = PipelineEvent(
        stage=stage,
        status=status,
        request_id=context.request_id,
        session_id=context.session_id,
        generation_id=context.generation_id,
        pipeline_id=context.pipeline_id,
        node_id=context.stage_id,
        agent=fields.pop("agent", None),
        worker=fields.pop("worker", None),
        model=fields.pop("model", None),
        provider=fields.pop("provider", None),
        parent_node=fields.pop("parent_node", None),
        warnings=tuple(warnings) if isinstance(warnings, (list, tuple)) else (),
        extra=fields,
        **typed,
    )
    bus.publish(event)
    return event.as_dict()


def get_events(generation_id: str) -> list[dict]:
    return _events._buffer.get(generation_id)  # noqa: SLF001


def elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)


@contextmanager
def stage_span(stage: str, **fields):
    parent = current_context()
    child = parent.child(
        stage_id=f"stage_{uuid4().hex[:12]}", parent_stage_id=parent.stage_id
    )
    token = bind_context(child)
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    emit_event(stage, "started", started_at=started_at, **fields)
    try:
        yield child.stage_id
    except Exception as exc:
        duration = elapsed_ms(started)
        emit_event(stage, "failed", duration_ms=duration,
                   started_at=started_at,
                   ended_at=datetime.now(timezone.utc).isoformat(),
                   exception=type(exc).__name__, **fields)
        raise
    else:
        duration = elapsed_ms(started)
        emit_event(stage, "completed", duration_ms=duration,
                   started_at=started_at,
                   ended_at=datetime.now(timezone.utc).isoformat(), **fields)
    finally:
        reset_context(token)
