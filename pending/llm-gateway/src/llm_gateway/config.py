"""YAML configuration loading for the gateway.

Example config file::

    rate_limit:
      requests_per_minute: 60
      burst: 10
    budgets:
      default: 5.0
    providers:
      - name: primary
        type: mock
        price_per_1k_prompt: 0.5
        price_per_1k_completion: 1.5
      - name: backup
        type: openai
        base_url: https://api.openai.com/v1
        api_key_env: OPENAI_API_KEY
    routes:
      - model_prefix: "gpt-"
        providers: [primary, backup]
      - providers: [primary]

No secrets are ever read from the YAML file itself -- provider API keys
are always resolved from environment variables named by `api_key_env`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from llm_gateway.cost_tracker import CostTracker
from llm_gateway.gateway import Gateway
from llm_gateway.providers.base import Provider
from llm_gateway.providers.mock import MockProvider
from llm_gateway.providers.openai_provider import OpenAICompatibleProvider
from llm_gateway.rate_limiter import RateLimiter
from llm_gateway.router import Router, RouteRule

_PROVIDER_BUILDERS = {
    "mock": lambda cfg: MockProvider(
        name=cfg["name"],
        price_per_1k_prompt=cfg.get("price_per_1k_prompt", 0.5),
        price_per_1k_completion=cfg.get("price_per_1k_completion", 1.5),
        latency_s=cfg.get("latency_s", 0.0),
    ),
    "openai": lambda cfg: OpenAICompatibleProvider(
        name=cfg["name"],
        base_url=cfg.get("base_url", "https://api.openai.com/v1"),
        api_key_env=cfg.get("api_key_env", "OPENAI_API_KEY"),
        price_per_1k_prompt=cfg.get("price_per_1k_prompt", 0.5),
        price_per_1k_completion=cfg.get("price_per_1k_completion", 1.5),
    ),
}


class ConfigError(ValueError):
    """Raised for structurally invalid gateway configuration."""


@dataclass
class GatewayConfig:
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_yaml(path: str | Path) -> GatewayConfig:
        text = Path(path).read_text(encoding="utf-8")
        return GatewayConfig.from_yaml_string(text)

    @staticmethod
    def from_yaml_string(text: str) -> GatewayConfig:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ConfigError("top-level config must be a mapping")
        return GatewayConfig(raw=data)

    def build_providers(self) -> dict[str, Provider]:
        providers: dict[str, Provider] = {}
        for entry in self.raw.get("providers", []):
            ptype = entry.get("type")
            builder = _PROVIDER_BUILDERS.get(ptype)
            if builder is None:
                raise ConfigError(f"unknown provider type: {ptype!r}")
            if "name" not in entry:
                raise ConfigError("every provider entry needs a 'name'")
            providers[entry["name"]] = builder(entry)
        if not providers:
            raise ConfigError("config must define at least one provider")
        return providers

    def build_router(self, providers: dict[str, Provider]) -> Router:
        rules = [
            RouteRule(
                providers=r["providers"],
                model_prefix=r.get("model_prefix"),
                task_hint=r.get("task_hint"),
            )
            for r in self.raw.get("routes", [])
        ]
        return Router(providers=providers, rules=rules)

    def build_gateway(self) -> Gateway:
        providers = self.build_providers()
        router = self.build_router(providers)

        rl_cfg = self.raw.get("rate_limit", {})
        rate_limiter = RateLimiter(
            requests_per_minute=rl_cfg.get("requests_per_minute", 60.0),
            burst=rl_cfg.get("burst"),
        )

        budgets = self.raw.get("budgets", {})
        cost_tracker = CostTracker(budget_usd=budgets)

        return Gateway(router=router, rate_limiter=rate_limiter, cost_tracker=cost_tracker)


DEFAULT_CONFIG_YAML = """\
rate_limit:
  requests_per_minute: 120
  burst: 20
budgets: {}
providers:
  - name: primary
    type: mock
    price_per_1k_prompt: 0.5
    price_per_1k_completion: 1.5
  - name: secondary
    type: mock
    price_per_1k_prompt: 0.3
    price_per_1k_completion: 0.9
routes:
  - providers: [primary, secondary]
"""
