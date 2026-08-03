import json

from toolschema_lint.linter import Linter
from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.report import format_json, format_sarif, format_text


def make_result():
    tools = [ToolSchema(name="t1", description=None, parameters=())]
    return Linter().lint(tools)


def test_format_text_includes_summary_line():
    result = make_result()
    out = format_text(result)
    assert "Checked 1 tool(s)" in out
    assert "error(s)" in out


def test_format_json_is_valid_and_matches_counts():
    result = make_result()
    out = format_json(result)
    payload = json.loads(out)
    assert payload["tool_count"] == 1
    assert payload["summary"]["errors"] == result.error_count
    assert len(payload["findings"]) == len(result.findings)


def test_format_sarif_is_valid_json_with_rules_and_results():
    result = make_result()
    out = format_sarif(result)
    payload = json.loads(out)
    assert payload["version"] == "2.1.0"
    run = payload["runs"][0]
    assert run["tool"]["driver"]["name"] == "toolschema-lint"
    assert len(run["results"]) == len(result.findings)


def test_finding_format_includes_parameter_when_present():
    f = Finding(
        rule_id="missing-parameter-description",
        severity=Severity.WARNING,
        message="no description",
        tool_name="my_tool",
        parameter_name="my_param",
    )
    assert "my_tool.my_param" in f.format()


def test_finding_format_omits_parameter_when_absent():
    f = Finding(
        rule_id="missing-tool-description",
        severity=Severity.ERROR,
        message="no description",
        tool_name="my_tool",
    )
    rendered = f.format()
    assert "my_tool:" in rendered
    assert "my_tool." not in rendered
