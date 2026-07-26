"""Command-line interface for agent-eval-harness.

Commands:
    agent-eval run --suite tasks.yaml --agent mock --store runs.jsonl
    agent-eval report --store runs.jsonl
    agent-eval compare --store runs.jsonl
"""

from __future__ import annotations

import importlib
import sys

import click
from rich.console import Console

from agent_eval_harness.report import compare_runs, render_regression, render_report
from agent_eval_harness.runner import AgentRunner, run_suite
from agent_eval_harness.storage import ResultStore
from agent_eval_harness.task import load_suite

console = Console()


def _load_agent(spec: str) -> AgentRunner:
    """Resolve an agent from a spec string.

    ``"mock"`` returns a built-in echoing :class:`MockAgent`. Anything of the form
    ``"module.submodule:factory_name"`` imports ``module.submodule`` and calls
    ``factory_name()`` to obtain an :class:`AgentRunner` instance.
    """
    if spec == "mock":
        from agent_eval_harness.mock_agent import MockAgent

        return MockAgent(fn=lambda prompt: prompt)

    if ":" not in spec:
        raise click.UsageError(
            f"Invalid --agent spec {spec!r}. Use 'mock' or 'module.path:factory_name'."
        )
    module_name, factory_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    return factory()


@click.group()
def cli() -> None:
    """agent-eval-harness: evaluate and regression-test LLM agents against task suites."""


@cli.command()
@click.option("--suite", "suite_path", required=True, type=click.Path(exists=True),
              help="Path to a YAML/JSON task suite file.")
@click.option("--agent", "agent_spec", default="mock",
              help="'mock' or 'module.path:factory_name' resolving to an AgentRunner.")
@click.option("--store", "store_path", default="runs.jsonl",
              help="JSONL file to append this run's results to.")
@click.option("--label", "agent_label", default=None,
              help="Human-readable label for this agent/run (defaults to the --agent spec).")
@click.option("--tag", "tag_filter", default=None, help="Only run tasks carrying this tag.")
@click.option("--fail-under", "fail_under", type=float, default=None,
              help="Exit non-zero if the suite's pass rate is below this threshold.")
def run(suite_path: str, agent_spec: str, store_path: str, agent_label: str | None,
        tag_filter: str | None, fail_under: float | None) -> None:
    """Run a task suite against an agent and persist the results."""
    suite = load_suite(suite_path)
    if tag_filter:
        suite = suite.filter_by_tag(tag_filter)
    if len(suite) == 0:
        console.print("[yellow]No tasks to run (empty suite after filtering).[/yellow]")
        sys.exit(0)

    agent = _load_agent(agent_spec)
    result = run_suite(agent, suite)
    render_report(result, console=console)

    store = ResultStore(store_path)
    store.save(result, agent_label=agent_label or agent_spec)

    if fail_under is not None and result.pass_rate < fail_under:
        console.print(
            f"[red bold]Pass rate {result.pass_rate:.1%} is below threshold {fail_under:.1%}[/red bold]"
        )
        sys.exit(1)


@cli.command()
@click.option("--store", "store_path", required=True, type=click.Path(exists=True),
              help="JSONL results store to read from.")
@click.option("--suite-name", "suite_name", default=None,
              help="Restrict to runs of this suite name.")
def report(store_path: str, suite_name: str | None) -> None:
    """Print a summary of the most recently stored run."""
    store = ResultStore(store_path)
    latest = store.latest(suite_name=suite_name)
    if latest is None:
        console.print("[yellow]No stored runs found.[/yellow]")
        sys.exit(1)
    console.print(f"[bold]Run:[/bold] {latest.run_id}  [bold]Agent:[/bold] {latest.agent_label}")
    console.print(f"[bold]Pass rate:[/bold] {latest.pass_rate:.1%}  "
                   f"[bold]Weighted score:[/bold] {latest.weighted_score:.3f}")


@cli.command()
@click.option("--store", "store_path", required=True, type=click.Path(exists=True),
              help="JSONL results store to read from.")
@click.option("--suite-name", "suite_name", default=None,
              help="Restrict comparison to runs of this suite name.")
@click.option("--fail-on-regression", is_flag=True, default=False,
              help="Exit non-zero if any task regressed relative to the previous run.")
def compare(store_path: str, suite_name: str | None, fail_on_regression: bool) -> None:
    """Compare the two most recent stored runs of a suite and report regressions."""
    store = ResultStore(store_path)
    current = store.latest(suite_name=suite_name)
    baseline = store.previous(suite_name=suite_name)
    if current is None or baseline is None:
        console.print("[yellow]Need at least two stored runs to compare.[/yellow]")
        sys.exit(1)

    regression_report = compare_runs(baseline, current)
    render_regression(regression_report, console=console)

    if fail_on_regression and regression_report.has_regressions:
        sys.exit(1)


if __name__ == "__main__":
    cli()
