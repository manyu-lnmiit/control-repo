"""A deterministic mock agent used in tests, examples, and CI where no real LLM is available."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MockAgent:
    """An :class:`AgentRunner` backed by a static lookup table or a callable.

    Useful for exercising the harness end-to-end (CLI, storage, reporting) without needing
    network access or API keys, and for unit-testing tasks/scorers in isolation.
    """

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        default: Any = "",
        fn: Callable[[str], Any] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default = default
        self.fn = fn

    def run(self, prompt: str) -> Any:
        if self.fn is not None:
            return self.fn(prompt)
        return self.responses.get(prompt, self.default)
