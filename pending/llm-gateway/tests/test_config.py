import pytest

from llm_gateway.config import DEFAULT_CONFIG_YAML, ConfigError, GatewayConfig


def test_default_config_builds_a_working_gateway():
    cfg = GatewayConfig.from_yaml_string(DEFAULT_CONFIG_YAML)
    gateway = cfg.build_gateway()
    assert set(gateway.providers.keys()) == {"primary", "secondary"}


def test_missing_provider_type_raises():
    cfg = GatewayConfig.from_yaml_string("providers:\n  - name: x\n    type: nope\n")
    with pytest.raises(ConfigError):
        cfg.build_providers()


def test_provider_without_name_raises():
    cfg = GatewayConfig.from_yaml_string("providers:\n  - type: mock\n")
    with pytest.raises(ConfigError):
        cfg.build_providers()


def test_no_providers_raises():
    cfg = GatewayConfig.from_yaml_string("providers: []\n")
    with pytest.raises(ConfigError):
        cfg.build_providers()


def test_top_level_must_be_mapping():
    with pytest.raises(ConfigError):
        GatewayConfig.from_yaml_string("- 1\n- 2\n")


def test_routes_are_parsed_into_rules():
    yaml_text = """
providers:
  - name: a
    type: mock
  - name: b
    type: mock
routes:
  - model_prefix: "gpt-"
    providers: [a]
  - providers: [b]
"""
    cfg = GatewayConfig.from_yaml_string(yaml_text)
    providers = cfg.build_providers()
    router = cfg.build_router(providers)
    assert len(router.rules) == 2
    assert router.rules[0].model_prefix == "gpt-"
