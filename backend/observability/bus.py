"""Centralized typed pipeline event bus.

Every DAG node and pipeline stage publishes a :class:`PipelineEvent`. The bus
fans each event out to subscribed sinks (structured logging, in-memory ring
buffer, metrics collectors, optional CLI timeline). Sinks are decoupled from
producers and a failing sink can never break a pipeline run.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class PipelineEvent:
    stage: str
    status: str
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    ended_at: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    generation_id: str | None = None
    pipeline_id: str | None = None
    node_id: str | None = None
    parent_node: str | None = None
    agent: str | None = None
    worker: str | None = None
    model: str | None = None
    provider: str | None = None
    duration_ms: int | None = None
    retry_count: int | None = None
    validation_status: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "generation_id": self.generation_id,
            "pipeline_id": self.pipeline_id,
            "node_id": self.node_id,
            "parent_node": self.parent_node,
            "stage": self.stage,
            "status": self.status,
            "agent": self.agent,
            "worker": self.worker,
            "model": self.model,
            "provider": self.provider,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "validation_status": self.validation_status,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "error": self.error,
            "warnings": list(self.warnings),
        }
        for key, value in self.extra.items():
            if value is not None:
                payload[key] = value
        return payload


class EventSink:
    def handle(self, event: PipelineEvent) -> None:
        raise NotImplementedError


class PipelineEventBus:
    def __init__(self) -> None:
        self._sinks: list[EventSink] = []

    def subscribe(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    def publish(self, event: PipelineEvent) -> None:
        for sink in list(self._sinks):
            try:
                sink.handle(event)
            except Exception:  # a sink must never break the pipeline
                continue


bus = PipelineEventBus()
