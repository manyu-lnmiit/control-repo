"""Render a compiled graph as a Mermaid flowchart for docs/READMEs/PRs."""

from __future__ import annotations

from .graph import END, START, CompiledGraph


def to_mermaid(graph: CompiledGraph, *, direction: str = "TD") -> str:
    """Return a ``mermaid`` flowchart definition string for ``graph``.

    Static edges render as solid arrows, conditional edges as dashed arrows
    labeled with the router's path key, and parallel (fan-out) edges as
    solid arrows from the same source.
    """
    lines = [f"flowchart {direction}"]
    lines.append(f'    {START}(["start"])')
    lines.append(f'    {END}(["end"])')
    for name in graph.nodes:
        lines.append(f"    {name}[{name}]")

    for source, edge in graph.edges.items():
        src = source
        if edge.kind == "conditional":
            assert edge.path_map is not None
            for key, target in edge.path_map.items():
                lines.append(f"    {src} -.{key}.-> {target}")
        else:
            for target in edge.targets:
                lines.append(f"    {src} --> {target}")

    for name in graph.nodes:
        if name not in graph.edges:
            lines.append(f"    {name} --> {END}")

    return "\n".join(lines)
