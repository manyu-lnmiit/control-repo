"""Human-readable reporting: terminal tables and run-over-run regression detection."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table

from agent_eval_harness.runner import SuiteRunResult
from agent_eval_harness.storage import StoredRun


@dataclass
class RegressionReport:
    """Diff between two runs of the same suite.

    Attributes:
        regressed: Task ids that passed in the baseline run but fail (or now error) now.
        fixed: Task ids that failed in the baseline run but pass now.
        new_tasks: Task ids present now but absent from the baseline.
        removed_tasks: Task ids present in the baseline but absent now.
        score_delta: ``current.weighted_score - baseline.weighted_score``.
    """

    regressed: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    new_tasks: list[str] = field(default_factory=list)
    removed_tasks: list[str] = field(default_factory=list)
    score_delta: float = 0.0

    @property
    def has_regressions(self) -> bool:
        return len(self.regressed) > 0


def compare_runs(baseline: StoredRun, current: StoredRun) -> RegressionReport:
    """Compare a ``current`` run against a ``baseline`` run of the same suite."""
    base_by_id = {r["task_id"]: r for r in baseline.results}
    cur_by_id = {r["task_id"]: r for r in current.results}

    regressed = [
        tid for tid, base_r in base_by_id.items()
        if tid in cur_by_id and base_r["passed"] and not cur_by_id[tid]["passed"]
    ]
    fixed = [
        tid for tid, base_r in base_by_id.items()
        if tid in cur_by_id and not base_r["passed"] and cur_by_id[tid]["passed"]
    ]
    new_tasks = [tid for tid in cur_by_id if tid not in base_by_id]
    removed_tasks = [tid for tid in base_by_id if tid not in cur_by_id]

    return RegressionReport(
        regressed=sorted(regressed),
        fixed=sorted(fixed),
        new_tasks=sorted(new_tasks),
        removed_tasks=sorted(removed_tasks),
        score_delta=current.weighted_score - baseline.weighted_score,
    )


def render_report(suite_result: SuiteRunResult, console: Console | None = None) -> str:
    """Render a rich table summarizing ``suite_result`` and return its plain-text form.

    If ``console`` is provided but was not constructed with ``record=True``, the table is
    still printed to it; an empty string is returned instead of raising, since export is
    only possible on a recording console.
    """
    console = console or Console(record=True, width=100)
    table = Table(title=f"Suite: {suite_result.suite_name}")
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Passed", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Latency (s)", justify="right")
    table.add_column("Detail", overflow="fold")

    for r in suite_result.results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        detail = r.error if r.error else (r.score_result.detail if r.score_result else "")
        table.add_row(r.task_id, status, f"{r.score:.2f}", f"{r.latency_s:.3f}", detail)

    console.print(table)
    console.print(
        f"[bold]Pass rate:[/bold] {suite_result.pass_rate:.1%}  "
        f"[bold]Weighted score:[/bold] {suite_result.weighted_score:.3f}"
    )
    return console.export_text() if console.record else ""


def render_regression(report: RegressionReport, console: Console | None = None) -> str:
    """Render a rich summary of a :class:`RegressionReport` and return its plain-text form."""
    console = console or Console(record=True, width=100)
    console.print(f"[bold]Score delta:[/bold] {report.score_delta:+.3f}")
    if report.regressed:
        console.print(f"[red bold]Regressed ({len(report.regressed)}):[/red bold] "
                       + ", ".join(report.regressed))
    if report.fixed:
        console.print(f"[green bold]Fixed ({len(report.fixed)}):[/green bold] "
                       + ", ".join(report.fixed))
    if report.new_tasks:
        console.print(f"[bold]New tasks:[/bold] {', '.join(report.new_tasks)}")
    if report.removed_tasks:
        console.print(f"[bold]Removed tasks:[/bold] {', '.join(report.removed_tasks)}")
    if not (report.regressed or report.fixed or report.new_tasks or report.removed_tasks):
        console.print("[dim]No changes detected.[/dim]")
    return console.export_text() if console.record else ""
