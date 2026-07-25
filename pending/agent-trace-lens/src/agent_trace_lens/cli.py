"""Command-line interface for agent-trace-lens."""

from __future__ import annotations

import json

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from agent_trace_lens.api import create_app
from agent_trace_lens.storage import SQLiteStorage

app = typer.Typer(help="Tracing, storage, and timeline visualization for multi-agent LLM systems.")
console = Console()


@app.command()
def serve(
    db: str = typer.Option("agent_trace_lens.db", help="Path to the SQLite trace database."),
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Run the trace query API and timeline viewer web server."""
    fastapi_app = create_app(db_path=db)
    uvicorn.run(fastapi_app, host=host, port=port)


@app.command(name="list")
def list_traces(
    db: str = typer.Option("agent_trace_lens.db", help="Path to the SQLite trace database."),
    limit: int = typer.Option(20, help="Maximum number of traces to show."),
) -> None:
    """List recent traces with summary stats."""
    storage = SQLiteStorage(db)
    traces = storage.list_traces(limit=limit)
    table = Table(title="Recent Traces")
    table.add_column("Trace ID")
    table.add_column("Root")
    table.add_column("Spans", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Duration (ms)", justify="right")
    for t in traces:
        table.add_row(
            t.trace_id,
            t.root_name or "-",
            str(t.span_count),
            str(t.error_count),
            f"{t.duration_ms:.1f}" if t.duration_ms is not None else "-",
        )
    console.print(table)


@app.command()
def show(
    trace_id: str = typer.Argument(..., help="Trace ID to display."),
    db: str = typer.Option("agent_trace_lens.db", help="Path to the SQLite trace database."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a table."),
) -> None:
    """Show every span recorded for a single trace."""
    storage = SQLiteStorage(db)
    spans = storage.get_trace(trace_id)
    if not spans:
        console.print(f"[red]No spans found for trace {trace_id}[/red]")
        raise typer.Exit(code=1)

    if as_json:
        console.print_json(json.dumps([s.model_dump() for s in spans], default=str))
        return

    table = Table(title=f"Trace {trace_id}")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Duration (ms)", justify="right")
    for s in spans:
        table.add_row(
            s.name,
            s.kind.value,
            s.status.value,
            f"{s.duration_ms:.1f}" if s.duration_ms is not None else "-",
        )
    console.print(table)


if __name__ == "__main__":
    app()
