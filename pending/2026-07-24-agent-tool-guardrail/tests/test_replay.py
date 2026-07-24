import pytest

from agent_guardrail.exceptions import ReplayMismatchError
from agent_guardrail.guard import guard
from agent_guardrail.replay import ReplayEngine
from agent_guardrail.tracing import TraceRecorder


def _record_session(policy, trace_path):
    tracer = TraceRecorder(trace_path, session_id="replay-test")

    @guard(policy=policy, tracer=tracer)
    def search_web(query: str) -> str:
        return f"results for {query}"

    @guard(policy=policy, tracer=tracer)
    def read_file(path: str) -> str:
        return f"contents of {path}"

    search_web(query="hello")
    read_file(path="/tmp/x")
    return tracer


def test_replay_next_output_matches_recording(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)

    assert replay.has_next()
    out1 = replay.next_output("search_web", {"query": "hello"})
    assert out1 == "results for hello"

    out2 = replay.next_output("read_file", {"path": "/tmp/x"})
    assert out2 == "contents of /tmp/x"

    assert not replay.has_next()


def test_replay_detects_tool_name_mismatch(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    with pytest.raises(ReplayMismatchError):
        replay.next_output("read_file")


def test_replay_detects_argument_mismatch(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    with pytest.raises(ReplayMismatchError):
        replay.next_output("search_web", {"query": "different"})


def test_replay_exhausted_raises(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    replay.next_output("search_web")
    replay.next_output("read_file")
    with pytest.raises(ReplayMismatchError):
        replay.next_output("search_web")


def test_replay_assert_matches_success(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    replay.assert_matches(
        [
            {"tool_name": "search_web", "arguments": {"query": "hello"}},
            {"tool_name": "read_file", "arguments": {"path": "/tmp/x"}},
        ]
    )


def test_replay_assert_matches_detects_drift(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    with pytest.raises(ReplayMismatchError):
        replay.assert_matches(
            [{"tool_name": "search_web", "arguments": {"query": "DIFFERENT"}}]
        )


def test_replay_reset(policy, trace_path):
    _record_session(policy, trace_path)
    replay = ReplayEngine(trace_path)
    replay.next_output("search_web")
    replay.reset()
    assert replay.has_next()
    out = replay.next_output("search_web", {"query": "hello"})
    assert out == "results for hello"
