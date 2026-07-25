from __future__ import annotations

import pytest

from agent_trace_lens.models import SpanKind, SpanStatus


def test_single_trace_records_root_span(tracer):
    with tracer.trace("run-1") as t:
        trace_id = t.trace_id

    spans = tracer.storage.get_trace(trace_id)
    assert len(spans) == 1
    assert spans[0].name == "run-1"
    assert spans[0].status == SpanStatus.OK
    assert spans[0].parent_id is None
    assert spans[0].duration_ms is not None


def test_nested_spans_capture_parent_child_relationship(tracer):
    with tracer.trace("planner-run") as t:
        trace_id = t.trace_id
        with tracer.span("search_web", kind=SpanKind.TOOL) as tool_span:
            tool_span.set_attribute("query", "weather in sf")
            with tracer.span("llm_call", kind=SpanKind.LLM) as llm_span:
                llm_span.set_tokens(tokens_in=120, tokens_out=45)

    spans = {s.name: s for s in tracer.storage.get_trace(trace_id)}
    assert set(spans) == {"planner-run", "search_web", "llm_call"}

    root = spans["planner-run"]
    tool = spans["search_web"]
    llm = spans["llm_call"]

    assert tool.parent_id == root.id
    assert llm.parent_id == tool.id
    assert tool.attributes["query"] == "weather in sf"
    assert llm.tokens_in == 120
    assert llm.tokens_out == 45


def test_span_records_error_and_reraises(tracer):
    with pytest.raises(ValueError):
        with tracer.trace("failing-run") as t:
            trace_id = t.trace_id
            with tracer.span("risky_tool", kind=SpanKind.TOOL):
                raise ValueError("boom")

    spans = {s.name: s for s in tracer.storage.get_trace(trace_id)}
    assert spans["risky_tool"].status == SpanStatus.ERROR
    assert "boom" in spans["risky_tool"].error
    # the failure inside the child should also mark the parent trace span as errored
    assert spans["failing-run"].status == SpanStatus.ERROR


def test_span_without_explicit_trace_creates_implicit_one(tracer):
    with tracer.span("standalone_tool", kind=SpanKind.TOOL) as s:
        trace_id = s.trace_id

    spans = tracer.storage.get_trace(trace_id)
    assert len(spans) == 1
    assert spans[0].parent_id is None


def test_instrument_decorator_wraps_function_in_span(tracer):
    @tracer.instrument(name="add_numbers", kind=SpanKind.TOOL)
    def add(a: int, b: int) -> int:
        return a + b

    with tracer.trace("decorated-run") as t:
        trace_id = t.trace_id
        result = add(2, 3)

    assert result == 5
    spans = {s.name: s for s in tracer.storage.get_trace(trace_id)}
    assert "add_numbers" in spans
    assert spans["add_numbers"].status == SpanStatus.OK


def test_concurrent_traces_do_not_leak_span_ids():
    """Sequentially interleaved traces (simulating separate requests) must not
    cross-contaminate parent/child relationships when contextvars reset properly."""
    import os
    import tempfile

    from agent_trace_lens.storage import SQLiteStorage
    from agent_trace_lens.tracer import Tracer

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        t = Tracer(storage=SQLiteStorage(path))

        with t.trace("run-a") as ta:
            trace_a = ta.trace_id
            with t.span("child-a"):
                pass

        with t.trace("run-b") as tb:
            trace_b = tb.trace_id
            with t.span("child-b"):
                pass

        spans_a = t.storage.get_trace(trace_a)
        spans_b = t.storage.get_trace(trace_b)
        assert len(spans_a) == 2
        assert len(spans_b) == 2
        assert trace_a != trace_b
    finally:
        os.remove(path)
