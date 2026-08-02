import threading
from contextlib import contextmanager

import pytest

from observability.context import bind_context, current_context, new_context, reset_context
from observability.events import emit_event, get_events, stage_span
from observability.metrics import metrics


@pytest.fixture(autouse=True)
def _fresh_metrics():
    metrics.counters.clear()
    metrics.timings.clear()
    yield


def test_context_roundtrip_and_defaults():
    ctx = new_context(request_id="req_test", session_id="sess_test")
    token = bind_context(ctx)
    try:
        assert current_context().request_id == "req_test"
        assert current_context().session_id == "sess_test"
    finally:
        reset_context(token)
    assert current_context().request_id != "req_test"


def test_context_is_not_shared_between_threads():
    observed = {}
    holder = new_context(request_id="req-main")
    token = bind_context(holder)
    try:
        def worker():
            observed["id"] = current_context().request_id

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert observed["id"] != "req-main"
        assert current_context().request_id == "req-main"
    finally:
        reset_context(token)


def test_emit_event_and_retrieval_keyed_by_generation():
    ctx = new_context()
    ctx.generation_id = "gen-abc"
    token = bind_context(ctx)
    try:
        emit_event("resume_optimization", "completed", duration_ms=120)
    finally:
        reset_context(token)

    events = get_events("gen-abc")
    assert len(events) == 1
    assert events[0]["stage"] == "resume_optimization"
    assert events[0]["status"] == "completed"
    assert events[0]["generation_id"] == "gen-abc"
    assert events[0]["duration_ms"] == 120


def test_stage_span_emits_started_completed():
    ctx = new_context()
    ctx.generation_id = "gen_span"
    token = bind_context(ctx)
    try:
        with stage_span("extract", component="test"):
            pass
    finally:
        reset_context(token)

    states = {e["status"] for e in get_events("gen_span")}
    assert {"started", "completed"} <= states


def test_stage_span_marks_failure():
    ctx = new_context()
    ctx.generation_id = "gen_fail"
    token = bind_context(ctx)
    try:
        with pytest.raises(RuntimeError):
            with stage_span("fail_stage", component="test"):
                raise RuntimeError("boom")
    finally:
        reset_context(token)

    events = get_events("gen_fail")
    assert any(e["status"] == "failed" and e["exception"] == "RuntimeError" for e in events)


def test_metrics_increment_and_prometheus_output():
    metrics.increment("resumeforge_requests_total", route="/api/generate", status=200)
    metrics.increment("resumeforge_requests_total", route="/api/generate", status=200)
    metrics.observe("resumeforge_generation_duration", 1500)

    output = metrics.prometheus()
    assert "resumeforge_requests_total" in output
    assert "resumeforge_generation_duration_count 1" in output