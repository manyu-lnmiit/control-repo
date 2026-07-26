import json
from pathlib import Path

from click.testing import CliRunner

from agent_eval_harness.cli import cli

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_cli_run_with_mock_agent(tmp_path):
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    result = runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", "mock",
         "--store", str(store_path)],
    )
    assert result.exit_code == 0, result.output
    assert store_path.exists()
    lines = store_path.read_text().strip().splitlines()
    assert len(lines) == 1


def test_cli_run_with_custom_agent_factory(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES_DIR.parent))
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    result = runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"),
         "--agent", "examples.demo_agent:make_agent", "--store", str(store_path)],
    )
    assert result.exit_code == 0, result.output
    record = json.loads(store_path.read_text().strip().splitlines()[0])
    assert record["pass_rate"] == 1.0


def test_cli_run_fail_under_threshold(tmp_path):
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    result = runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", "mock",
         "--store", str(store_path), "--fail-under", "0.99"],
    )
    assert result.exit_code == 1


def test_cli_report_no_runs(tmp_path):
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    store_path.touch()
    result = runner.invoke(cli, ["report", "--store", str(store_path)])
    assert result.exit_code == 1


def test_cli_report_after_run(tmp_path):
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", "mock",
         "--store", str(store_path)],
    )
    result = runner.invoke(cli, ["report", "--store", str(store_path)])
    assert result.exit_code == 0
    assert "Pass rate" in result.output


def test_cli_compare_needs_two_runs(tmp_path):
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", "mock",
         "--store", str(store_path)],
    )
    result = runner.invoke(cli, ["compare", "--store", str(store_path)])
    assert result.exit_code == 1
    assert "at least two" in result.output


def test_cli_compare_two_runs(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES_DIR.parent))
    runner = CliRunner()
    store_path = tmp_path / "runs.jsonl"
    for agent_spec in ["mock", "examples.demo_agent:make_agent"]:
        runner.invoke(
            cli,
            ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", agent_spec,
             "--store", str(store_path)],
        )
    result = runner.invoke(cli, ["compare", "--store", str(store_path)])
    assert result.exit_code == 0
    assert "Score delta" in result.output


def test_cli_run_invalid_agent_spec(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["run", "--suite", str(EXAMPLES_DIR / "tasks.yaml"), "--agent", "not-a-valid-spec",
         "--store", str(tmp_path / "runs.jsonl")],
    )
    assert result.exit_code != 0
