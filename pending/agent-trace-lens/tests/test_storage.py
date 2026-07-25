from __future__ import annotations

import time

from agent_trace_lens.models import Span, SpanKind, SpanStatus


def _make_span(trace_id: str, span_id: str, parent_id=None, **overrides) -> Span:
    base = dict(
        id=span_id,
        trace_id=trace_id,
        parent_id=parent_id,
        name=f"span-{span_id}",
        kind=SpanKind.TOOL,
        start_time=time.time(),
        end_time=time.time() + 0.01,
        status=SpanStatus.OK,
        attributes={"k": "v"},
        tokens_in=10,
        tokens_out=5,
    )
    base.update(overrides)
    return Span(**base)


def test_upsert_and_get_span_round_trip(storage):
    s = _make_span("t1", "s1")
    storage.upsert_span(s)

    fetched = storage.get_span("s1")
    assert fetched is not None
    assert fetched.name == "span-s1"
    assert fetched.attributes == {"k": "v"}
    assert fetched.tokens_in == 10


def test_upsert_updates_existing_span_on_conflict(storage):
    s = _make_span("t1", "s1", status=SpanStatus.RUNNING, end_time=None)
    storage.upsert_span(s)

    s.status = SpanStatus.OK
    s.end_time = time.time()
    storage.upsert_span(s)

    fetched = storage.get_span("s1")
    assert fetched.status == SpanStatus.OK
    assert fetched.end_time is not None


def test_get_trace_orders_by_start_time(storage):
    now = time.time()
    storage.upsert_span(_make_span("t1", "s2", start_time=now + 1))
    storage.upsert_span(_make_span("t1", "s1", start_time=now))

    spans = storage.get_trace("t1")
    assert [s.id for s in spans] == ["s1", "s2"]


def test_list_traces_aggregates_correctly(storage):
    storage.upsert_span(_make_span("t1", "s1", parent_id=None))
    storage.upsert_span(_make_span("t1", "s2", parent_id="s1", status=SpanStatus.ERROR))
    storage.upsert_span(_make_span("t2", "s3", parent_id=None))

    summaries = {t.trace_id: t for t in storage.list_traces()}
    assert summaries["t1"].span_count == 2
    assert summaries["t1"].error_count == 1
    assert summaries["t2"].span_count == 1
    assert summaries["t2"].error_count == 0


def test_delete_trace_removes_all_its_spans(storage):
    storage.upsert_span(_make_span("t1", "s1"))
    storage.upsert_span(_make_span("t1", "s2"))
    storage.upsert_span(_make_span("t2", "s3"))

    storage.delete_trace("t1")

    assert storage.get_trace("t1") == []
    assert len(storage.get_trace("t2")) == 1


def test_get_span_returns_none_for_missing_id(storage):
    assert storage.get_span("does-not-exist") is None
