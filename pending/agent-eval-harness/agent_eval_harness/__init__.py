"""agent-eval-harness: a task-based evaluation and regression harness for LLM agents.

Public API re-exports the most commonly used building blocks so callers can do::

    from agent_eval_harness import Task, TaskSuite, run_suite, ExactMatch
"""

from agent_eval_harness.mock_agent import MockAgent
from agent_eval_harness.report import RegressionReport, compare_runs, render_report
from agent_eval_harness.runner import AgentRunner, RunResult, SuiteRunResult, run_suite, run_task
from agent_eval_harness.scorers import (
    Composite,
    Contains,
    ExactMatch,
    NumericTolerance,
    RegexMatch,
    Scorer,
    ScoreResult,
)
from agent_eval_harness.storage import ResultStore
from agent_eval_harness.task import Task, TaskSuite, load_suite

__all__ = [
    "AgentRunner",
    "Composite",
    "Contains",
    "ExactMatch",
    "MockAgent",
    "NumericTolerance",
    "RegexMatch",
    "RegressionReport",
    "ResultStore",
    "RunResult",
    "ScoreResult",
    "Scorer",
    "SuiteRunResult",
    "Task",
    "TaskSuite",
    "compare_runs",
    "load_suite",
    "render_report",
    "run_suite",
    "run_task",
]

__version__ = "0.1.0"
