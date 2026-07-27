"""Core durable-execution primitives: :class:`Workflow` and the step decorator.

Design summary
---------------
A ``Workflow`` wraps a run identified by ``run_id`` and a :class:`~agentflow.store.Store`.
Functions decorated with ``@workflow.step(name)`` become *checkpointed steps*:

* Before executing, the runtime checks the store for a previously
  ``completed`` record for ``(run_id, step_name)``. If found, the cached
  result is returned immediately and the wrapped function body does not
  run again. This is what makes a crashed/restarted workflow resumable
  without side effects (e.g. an LLM call or a paid API request) being
  repeated for steps that already succeeded.
* On failure, the step is retried up to ``max_retries`` times with
  exponential backoff + jitter, persisting each attempt's outcome.
* ``workflow.approval_gate(name)`` lets a step pause the entire workflow for
  a human decision. It raises :class:`~agentflow.exceptions.ApprovalPending`
  the first time it's reached (persisting a ``waiting`` run status); once
  the gate is approved out-of-band (e.g. via the CLI) re-invoking
  ``workflow.run(...)`` will pass straight through the gate.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from .exceptions import ApprovalPending, StepFailed, WorkflowFailed
from .retry import compute_backoff
from .store import Store


class Workflow:
    """Orchestrates a single durable, resumable workflow run."""

    def __init__(self, name: str, run_id: str, store: Store):
        self.name = name
        self.run_id = run_id
        self.store = store
        self.store.ensure_run(run_id, name)

    # -- step decorator ---------------------------------------------------

    def step(
        self,
        step_name: str,
        max_retries: int = 0,
        backoff_base: float = 0.5,
        backoff_cap: float = 30.0,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        """Decorator that turns ``fn`` into a checkpointed workflow step.

        The decorated function must return a JSON-serializable value (it is
        persisted to the store as the step's checkpoint).
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                cached = self.store.get_step(self.run_id, step_name)
                if cached is not None and cached.status == "completed":
                    return cached.result

                attempt = cached.attempts if cached is not None else 0
                last_exc: BaseException | None = None

                while attempt <= max_retries:
                    try:
                        self.store.mark_running(self.run_id, step_name, attempt)
                        result = fn(*args, **kwargs)
                        self.store.mark_completed(
                            self.run_id, step_name, result, attempt
                        )
                        return result
                    except ApprovalPending:
                        # Not a step failure -- propagate untouched so the
                        # workflow can pause at the gate.
                        raise
                    except retry_on as exc:  # type: ignore[misc]
                        last_exc = exc
                        self.store.mark_failed(
                            self.run_id, step_name, repr(exc), attempt
                        )
                        if attempt >= max_retries:
                            break
                        delay = compute_backoff(attempt, backoff_base, backoff_cap)
                        sleep_fn(delay)
                        attempt += 1

                raise StepFailed(step_name, last_exc)

            wrapper.step_name = step_name  # type: ignore[attr-defined]
            return wrapper

        return decorator

    # -- human-in-the-loop approval gates ----------------------------------

    def approval_gate(self, gate_name: str) -> bool:
        """Block the workflow at ``gate_name`` until it is externally approved.

        Returns ``True`` if the gate is already approved (allowing the
        caller to proceed inline). Otherwise records the gate as pending and
        raises :class:`ApprovalPending`.
        """
        status = self.store.get_gate(self.run_id, gate_name)
        if status == "approved":
            return True
        self.store.request_gate(self.run_id, gate_name)
        raise ApprovalPending(self.run_id, gate_name)

    # -- run orchestration --------------------------------------------------

    def run(self, entrypoint: Callable[[Workflow], Any]) -> Any:
        """Execute (or resume) the workflow by calling ``entrypoint(self)``.

        ``entrypoint`` should call one or more ``@workflow.step``-decorated
        functions and/or ``workflow.approval_gate``. Re-invoking ``run`` on
        the same ``run_id`` after a crash or an ``ApprovalPending`` pause
        will skip already-completed steps and resume from where it left off.
        """
        try:
            result = entrypoint(self)
            self.store.mark_run_completed(self.run_id, result)
            return result
        except ApprovalPending as ap:
            self.store.mark_run_waiting(self.run_id, ap.gate_name)
            raise
        except StepFailed as sf:
            self.store.mark_run_failed(self.run_id, str(sf))
            raise WorkflowFailed(self.run_id, sf) from sf
