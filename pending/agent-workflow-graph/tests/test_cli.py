import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "agentworkflow.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )


def test_cli_run_example_research_workflow():
    proc = _run_cli(
        "run",
        "--graph",
        "examples.research_workflow:build_graph",
        "--input",
        json.dumps({"topic": "rust vs go"}),
    )
    assert proc.returncode == 0, proc.stderr
    state = json.loads(proc.stdout)
    assert "final_report" in state
    assert state["score"] >= 0.9


def test_cli_visualize_example_research_workflow():
    proc = _run_cli("visualize", "--graph", "examples.research_workflow:build_graph")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("flowchart TD")
    assert "critique" in proc.stdout


def test_cli_run_rejects_bad_graph_spec():
    proc = _run_cli("run", "--graph", "not-a-valid-spec")
    assert proc.returncode != 0
