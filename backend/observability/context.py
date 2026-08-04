"""Correlation context propagated through async and worker-thread execution."""

from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from time import perf_counter
from uuid import uuid4


@dataclass
class ObservabilityContext:
    request_id: str
    session_id: str
    generation_id: str | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    parent_stage_id: str | None = None
    started_at: float = field(default_factory=perf_counter)

    def child(self, **changes) -> "ObservabilityContext":
        """Fresh context derived from this one (used to isolate concurrent spans)."""
        return replace(self, **changes)


_context: ContextVar[ObservabilityContext | None] = ContextVar(
    "observability_context", default=None
)


def new_context(
    request_id: str | None = None, session_id: str | None = None
) -> ObservabilityContext:
    return ObservabilityContext(
        request_id or f"req_{uuid4().hex[:12]}",
        session_id or f"sess_{uuid4().hex[:12]}",
    )


def bind_context(context: ObservabilityContext):
    return _context.set(context)


def reset_context(token) -> None:
    _context.reset(token)


def current_context() -> ObservabilityContext:
    context = _context.get()
    if context is None:
        context = new_context()
        _context.set(context)
    return context