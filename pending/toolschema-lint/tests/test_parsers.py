import json
from pathlib import Path

import pytest

from toolschema_lint.parsers import detect_format, parse

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_parse_openai_clean():
    doc = load("openai_clean.json")
    tools = parse(doc, "openai")
    assert len(tools) == 2
    weather = tools[0]
    assert weather.name == "get_current_weather"
    assert weather.description.startswith("Fetch the current weather")
    assert len(weather.parameters) == 2
    city = weather.get_parameter("city")
    assert city.required is True
    assert city.type == "string"
    unit = weather.get_parameter("unit")
    assert unit.enum == ["celsius", "fahrenheit"]
    assert unit.required is False


def test_parse_anthropic_clean():
    doc = load("anthropic_clean.json")
    tools = parse(doc, "anthropic")
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "lookup_order_status"
    assert tool.get_parameter("order_id").required is True


def test_parse_mcp_clean():
    doc = load("mcp_clean.json")
    tools = parse(doc, "mcp")
    assert len(tools) == 1
    assert tools[0].name == "read_file"
    assert tools[0].source_format == "mcp"


def test_detect_format_openai():
    doc = load("openai_clean.json")
    assert detect_format(doc) == "openai"


def test_detect_format_anthropic():
    doc = load("anthropic_clean.json")
    assert detect_format(doc) == "anthropic"


def test_detect_format_mcp():
    doc = load("mcp_clean.json")
    assert detect_format(doc) == "mcp"


def test_detect_format_unrecognizable_raises():
    with pytest.raises(ValueError):
        detect_format({"nothing": "here"})


def test_parse_unknown_format_raises():
    with pytest.raises(ValueError):
        parse([], "cohere")


def test_parser_skips_non_dict_entries():
    tools = parse([{"name": "a", "input_schema": {}}, "not-a-dict", 123], "anthropic")
    assert len(tools) == 1
    assert tools[0].name == "a"


def test_parser_handles_missing_name():
    tools = parse([{"description": "no name here"}], "anthropic")
    assert tools[0].name == "<unnamed-0>"
