import pytest

from prompt_registry.template import MissingVariableError, extract_variables, render_template


def test_extract_variables_ordered_and_deduped():
    body = "Hi {{name}}, your order {{order_id}} for {{name}} shipped."
    assert extract_variables(body) == ["name", "order_id"]


def test_render_template_basic_substitution():
    assert render_template("Hello, {{name}}!", {"name": "Ada"}) == "Hello, Ada!"


def test_render_template_uses_default_when_missing():
    assert render_template("Hi {{name|default(\"friend\")}}", {}) == "Hi friend"


def test_render_template_supplied_value_overrides_default():
    assert render_template("Hi {{name|default(\"friend\")}}", {"name": "Ada"}) == "Hi Ada"


def test_render_template_raises_on_missing_required_variable():
    with pytest.raises(MissingVariableError):
        render_template("Hi {{name}}", {})


def test_render_template_reports_all_missing_variables():
    with pytest.raises(MissingVariableError) as exc_info:
        render_template("{{a}} and {{b}}", {})
    message = str(exc_info.value)
    assert "a" in message and "b" in message


def test_render_template_handles_no_placeholders():
    assert render_template("static text", {}) == "static text"


def test_render_template_non_string_values_are_stringified():
    assert render_template("count={{n}}", {"n": 42}) == "count=42"
