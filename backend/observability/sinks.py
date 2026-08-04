"""Concrete sinks for the pipeline event bus.

Producers remain ignorant of consumers; adding or swapping a sink is a wiring
change only.
"""

import logging
import sys
import threading
from collections import defaultdict, deque

from .bus import PipelineEvent

logger = logging.getLogger("resumeforge.pipeline")


class JsonLogSink:
    """Emit every event as a structured JSON log line (legacy behavior)."""

    def handle(self, event: PipelineEvent) -> None:
        logger.info("pipeline_event", extra={"observability": event.as_dict()})


class BufferSink:
    """In-memory, per-pipeline ring buffer of events for diagnostics/timeline."""

    def __init__(self, capacity: int = 200, max_pipelines: int = 10_000) -> None:
        self.capacity = capacity
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=capacity))
        self._lock = threading.Lock()

    def handle(self, event: PipelineEvent) -> None:
        pipeline = event.generation_id or event.pipeline_id
        if not pipeline:
            return
        with self._lock:
            self._buffers[pipeline].append(event.as_dict())

    def get(self, generation_id: str) -> list[dict]:
        with self._lock:
            return list(self._buffers.get(generation_id, ()))


class MetricsSink:
    """Turn lifecycle events into counters/timings on the metrics registry."""

    def __init__(self, metrics) -> None:
        self._metrics = metrics

    def handle(self, event: PipelineEvent) -> None:
        self._metrics.increment(
            "resumeforge_pipeline_events_total",
            stage=event.stage,
            status=event.status,
        )
        if event.validation_status is not None:
            self._metrics.increment(
                "resumeforge_validation_total",
                task=event.stage,
                status=event.validation_status,
            )
        if event.duration_ms is not None:
            self._metrics.observe(
                "resumeforge_dag_node_duration",
                event.duration_ms,
                stage=event.stage,
                status=event.status,
            )
        if event.estimated_cost_usd:
            self._metrics.increment(
                "resumeforge_ai_cost_microusd_total",
                value=round(event.estimated_cost_usd * 1_000_000),
                stage=event.stage,
            )


class CLILineSink:
    """Human-readable timeline lines for local debugging (off by default)."""

    def __init__(self, logger_name: str = "resumeforge.timeline") -> None:
        self._stream = logging.getLogger(logger_name)

    def handle(self, event: PipelineEvent) -> None:
        who = event.worker or event.agent or event.node_id or ""
        line = f"[{event.stage:<22}] {event.status:<10} {who} "
        if event.duration_ms is not None:
            line += f"{event.duration_ms:>6}ms "
        if event.total_tokens is not None:
            line += f"tok={event.total_tokens} cost=${event.estimated_cost_usd or 0:.6f}"
        self._stream.info(line.strip())
