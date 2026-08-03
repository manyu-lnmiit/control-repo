import json
from pathlib import Path

import pytest

from toolschema_lint.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_validate_clean_schema_exits_zero(capsys):
    exit_code = main(["validate", str(FIXTURES / "openai_clean.json")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 error(s)" in captured.out


def test_cli_validate_problematic_schema_exits_nonzero(capsys):
    exit_code = main(["validate", str(FIXTURES / "openai_problematic.json")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error(s)" in captured.out


def test_cli_validate_fail_on_never_always_exits_zero():
    exit_code = main(
        ["validate", str(FIXTURES / "openai_problematic.json"), "--fail-on", "never"]
    )
    assert exit_code == 0


def test_cli_validate_json_output_is_parseable(capsys):
    main(["validate", str(FIXTURES / "openai_clean.json"), "--output", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["tool_count"] == 2


def test_cli_validate_explicit_format(capsys):
    exit_code = main(
        ["validate", str(FIXTURES / "anthropic_clean.json"), "--format", "anthropic"]
    )
    assert exit_code == 0


def test_cli_validate_missing_file_returns_error(capsys):
    exit_code = main(["validate", str(FIXTURES / "does_not_exist.json")])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Error reading" in captured.err


def test_cli_rules_lists_all_rules(capsys):
    exit_code = main(["rules"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "missing-tool-description" in captured.out
    assert "overlapping-tool-purpose" in captured.out


def test_cli_validate_with_config_file(tmp_path, capsys):
    config_path = tmp_path / "cfg.json"
    config_path.write_text(json.dumps({"disable": ["missing-tool-description"]}))
    exit_code = main(
        [
            "validate",
            str(FIXTURES / "openai_problematic.json"),
            "--config",
            str(config_path),
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    rule_ids = {f["rule_id"] for f in payload["findings"]}
    assert "missing-tool-description" not in rule_ids
    assert exit_code == 1


def test_main_with_no_command_prints_help(capsys):
    with pytest.raises(SystemExit):
        main([])
