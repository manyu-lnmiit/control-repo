import json
from pathlib import Path

from toolschema_lint.config import Config
from toolschema_lint.linter import Linter
from toolschema_lint.parsers import parse

FIXTURES = Path(__file__).parent / "fixtures"


def load_tools(name, fmt):
    doc = json.loads((FIXTURES / name).read_text())
    return parse(doc, fmt)


def rule_ids(result):
    return {f.rule_id for f in result.findings}


def test_clean_openai_schema_has_no_errors():
    tools = load_tools("openai_clean.json", "openai")
    result = Linter().lint(tools)
    assert result.error_count == 0


def test_missing_tool_description_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "missing-tool-description"]
    assert any(f.tool_name == "run" for f in findings)


def test_thin_tool_description_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "thin-tool-description"]
    assert any(f.tool_name == "run2" for f in findings)


def test_vague_tool_name_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "vague-tool-name"]
    assert any(f.tool_name == "run" for f in findings)


def test_required_parameter_not_defined_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "required-parameter-not-defined"]
    assert any(f.parameter_name == "missing_param" for f in findings)


def test_invalid_parameter_type_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "invalid-parameter-type"]
    assert any(f.parameter_name == "count" for f in findings)


def test_enum_value_type_mismatch_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "enum-value-type-mismatch"]
    assert any(f.parameter_name == "level" for f in findings)


def test_missing_enum_constraint_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "missing-enum-constraint"]
    assert any(f.parameter_name == "mode" for f in findings)


def test_boolean_naming_convention_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "boolean-naming-convention"]
    assert any(f.parameter_name == "flag" for f in findings)


def test_unconstrained_object_parameter_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "unconstrained-object-parameter"]
    assert any(f.parameter_name == "config" for f in findings)


def test_overlapping_tool_purpose_detected():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "overlapping-tool-purpose"]
    names = {f.tool_name for f in findings}
    assert "get_weather_report" in names or "fetch_weather_report" in names


def test_duplicate_tool_name_detected():
    tools = load_tools("openai_clean.json", "openai") + load_tools("openai_clean.json", "openai")
    result = Linter().lint(tools)
    findings = [f for f in result.findings if f.rule_id == "duplicate-tool-name"]
    assert len(findings) == 2  # both duplicated tools flagged


def test_disabled_rule_produces_no_findings():
    tools = load_tools("openai_problematic.json", "openai")
    config = Config(disabled_rules={"missing-tool-description"})
    result = Linter(config=config).lint(tools)
    assert "missing-tool-description" not in rule_ids(result)


def test_severity_override_changes_severity():
    tools = load_tools("openai_problematic.json", "openai")
    config = Config.from_dict({"severity": {"boolean-naming-convention": "error"}})
    result = Linter(config=config).lint(tools)
    overridden = [f for f in result.findings if f.rule_id == "boolean-naming-convention"]
    assert overridden and all(f.severity.value == "error" for f in overridden)


def test_similarity_threshold_config_applied():
    tools = load_tools("openai_problematic.json", "openai")
    strict_config = Config.from_dict({"similarity_threshold": 0.99})
    result = Linter(config=strict_config).lint(tools)
    findings = [f for f in result.findings if f.rule_id == "overlapping-tool-purpose"]
    assert findings == []


def test_lint_result_sorting_puts_errors_first():
    tools = load_tools("openai_problematic.json", "openai")
    result = Linter().lint(tools)
    ranks = [f.severity.rank for f in result.sorted_findings()]
    assert ranks == sorted(ranks, reverse=True)
