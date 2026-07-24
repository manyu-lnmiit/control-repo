from agent_guardrail.tracing import TraceEvent, TraceRecorder


def test_record_and_load_roundtrip(trace_path):
    tracer = TraceRecorder(trace_path, session_id="s1")
    call_id = tracer.next_call_id()
    tracer.record(
        TraceEvent(
            call_id=call_id,
            tool_name="search_web",
            arguments={"query": "hi"},
            decision="allowed",
            output="result",
            cost=0.01,
            duration_ms=12.3,
            started_at=1000.0,
            session_id="s1",
        )
    )
    loaded = TraceRecorder.load(trace_path)
    assert len(loaded) == 1
    assert loaded[0].tool_name == "search_web"
    assert loaded[0].output == "result"
    assert loaded[0].session_id == "s1"


def test_next_call_id_increments(trace_path):
    tracer = TraceRecorder(trace_path)
    ids = [tracer.next_call_id() for _ in range(5)]
    assert ids == [0, 1, 2, 3, 4]


def test_load_missing_file_returns_empty(tmp_path):
    missing = str(tmp_path / "nope.jsonl")
    assert TraceRecorder.load(missing) == []


def test_events_property_is_a_copy(trace_path):
    tracer = TraceRecorder(trace_path)
    tracer.record(
        TraceEvent(call_id=0, tool_name="t", arguments={}, decision="allowed")
    )
    events = tracer.events
    events.append("mutation")
    assert len(tracer.events) == 1
