"""Rule-based routing from a chat request to an ordered provider chain.

A :class:`RouteRule` matches requests by model-name prefix and/or an
optional ``task_hint`` (e.g. "summarization", "code"), and resolves to an
ordered list of provider names. The first provider in the list is the
primary; the rest form the failover chain used by :mod:`llm_gateway.retry`.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm_gateway.models import ChatRequest
from llm_gateway.providers.base import Provider


@dataclass
class RouteRule:
    """A single routing rule.

    ``model_prefix`` and ``task_hint`` are both optional matchers; a rule
    with neither set acts as a catch-all default. Rules are evaluated in
    the order they were registered and the first match wins.
    """

    providers: list[str]
    model_prefix: str | None = None
    task_hint: str | None = None

    def matches(self, request: ChatRequest) -> bool:
        if self.model_prefix and not request.model.startswith(self.model_prefix):
            return False
        return not (self.task_hint and request.task_hint != self.task_hint)


class RoutingError(RuntimeError):
    """Raised when no route and no fallback provider is available."""


class Router:
    """Resolves a :class:`ChatRequest` to an ordered provider chain."""

    def __init__(self, providers: dict[str, Provider], rules: list[RouteRule] | None = None):
        if not providers:
            raise ValueError("router requires at least one registered provider")
        self.providers = providers
        self.rules = rules or []

    def add_rule(self, rule: RouteRule) -> None:
        self.rules.append(rule)

    def resolve(self, request: ChatRequest) -> list[Provider]:
        """Return the ordered chain of providers to attempt for this request."""
        for rule in self.rules:
            if rule.matches(request):
                chain = [self.providers[name] for name in rule.providers if name in self.providers]
                if chain:
                    return chain
        # No rule matched (or matched rule had no live providers): fall back
        # to every registered provider in registration order.
        return list(self.providers.values())
