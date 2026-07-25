"""Instrumentation SDK: context managers and decorators for recording spans.

Typical usage::

    from agent_trace_lens import trace, span

    with trace("customer-support-run") as t:
        with span("planner", kind="agent"):
            ...
        with span("search_web", kind="tool") as s:
            s.set_attribute("query", "refund policy")
            ...
"""

from __future__ import annotations

import contextvars
import functools
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from agent_trace_lens.models import Span, SpanKind, SpanStatus
from agent_trace_lens.storage import SQLiteStorage, StorageBackend

_current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_trace_lens_current_trace_id", default=None
)
_current_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_trace_lens_current_span_id", default=None
)

_tracer_singleton: Optional["Tracer"] = None


class LiveSpan:
    """A handle to an in-flight span, returned by `span()` for attribute mutation."""

    def __init__(self, tracer: "Tracer", span_obj: Span):
        self._tracer = tracer
        self._span = span_obj

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.attributes[key] = value

    def set_tokens(self, tokens_in: Optional[int] = None, tokens_out: Optional[int] = None) -> None:
        if tokens_in is not None:
            self._span.tokens_in = tokens_in
        if tokens_out is not None:
            self._span.tokens_out = tokens_out

    @property
    def span_id(self) -> str:
        return self._span.id

    @property
    def trace_id(self) -> str:
        return self._span.trace_id


class Tracer:
    """Owns a storage backend and records spans into it."""

    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage: StorageBackend = storage or SQLiteStorage()

    @contextmanager
    def trace(self, name: str, trace_id: Optional[str] = None) -> Iterator[LiveSpan]:
        """Start a brand-new trace with a root span named `name`."""
        tid = trace_id or uuid.uuid4().hex
        token = _current_trace_id.set(tid)
        try:
            with self._span_ctx(name, kind=SpanKind.AGENT) as live_span:
                yield live_span
        finally:
            _current_trace_id.reset(token)

    @contextmanager
    def span(self, name: str, kind: SpanKind | str = SpanKind.CUSTOM) -> Iterator[LiveSpan]:
        """Start a child span within the current trace (or a new implicit trace)."""
        with self._span_ctx(name, kind=kind) as live_span:
            yield live_span

    @contextmanager
    def _span_ctx(self, name: str, kind: SpanKind | str) -> Iterator[LiveSpan]:
        if isinstance(kind, str):
            kind = SpanKind(kind)

        trace_id = _current_trace_id.get()
        implicit_trace = trace_id is None
        if implicit_trace:
            trace_id = uuid.uuid4().hex
            trace_token = _current_trace_id.set(trace_id)
        else:
            trace_token = None

        parent_id = _current_span_id.get()
        span_id = uuid.uuid4().hex
        span_obj = Span(
            id=span_id,
            trace_id=trace_id,
            parent_id=parent_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            status=SpanStatus.RUNNING,
        )
        self.storage.upsert_span(span_obj)
        span_token = _current_span_id.set(span_id)
        live_span = LiveSpan(self, span_obj)
        try:
            yield live_span
        except Exception as exc:
            span_obj.status = SpanStatus.ERROR
            span_obj.error = f"{type(exc).__name__}: {exc}"
            raise
        else:
            span_obj.status = SpanStatus.OK
        finally:
            span_obj.end_time = time.time()
            self.storage.upsert_span(span_obj)
            _current_span_id.reset(span_token)
            if trace_token is not None:
                _current_trace_id.reset(trace_token)

    def instrument(self, name: Optional[str] = None, kind: SpanKind | str = SpanKind.CUSTOM):
        """Decorator form: wraps a function call in a span."""

        def decorator(func):
            span_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.span(span_name, kind=kind):
                    return func(*args, **kwargs)

            return wrapper

        return decorator


def get_tracer(storage: Optional[StorageBackend] = None) -> Tracer:
    """Return the process-wide default Tracer, creating it on first use."""
    global _tracer_singleton
    if _tracer_singleton is None or storage is not None:
        _tracer_singleton = Tracer(storage=storage)
    return _tracer_singleton


def trace(name: str, trace_id: Optional[str] = None):
    """Convenience wrapper around `get_tracer().trace(...)`."""
    return get_tracer().trace(name, trace_id=trace_id)


def span(name: str, kind: SpanKind | str = SpanKind.CUSTOM):
    """Convenience wrapper around `get_tracer().span(...)`."""
    return get_tracer().span(name, kind=kind)
