"""Command-line interface for inspecting and managing an on-disk semantic cache."""

from __future__ import annotations

import click

from semantic_cache.cache import SemanticCache


@click.group()
def main() -> None:
    """semcache: inspect and manage an llm-semantic-cache database."""


@main.command()
@click.option("--path", default="semantic_cache.db", show_default=True, help="Path to the cache SQLite file.")
@click.option("--namespace", default=None, help="Restrict stats to a single namespace.")
def stats(path: str, namespace: str | None) -> None:
    """Print entry count, total hits, and estimated cost saved."""
    with SemanticCache(path=path) as cache:
        data = cache.stats(namespace=namespace)
        click.echo(f"entries:               {data['entries']}")
        click.echo(f"total_hits:            {data['total_hits']}")
        click.echo(f"estimated_cost_saved:  ${data['estimated_cost_saved']:.4f}")


@main.command()
@click.option("--path", default="semantic_cache.db", show_default=True, help="Path to the cache SQLite file.")
@click.option("--namespace", default=None, help="Only clear a single namespace.")
@click.confirmation_option(prompt="Are you sure you want to clear the cache?")
def clear(path: str, namespace: str | None) -> None:
    """Delete all cached entries (or all entries in one namespace)."""
    with SemanticCache(path=path) as cache:
        removed = cache.clear(namespace=namespace)
        click.echo(f"removed {removed} entries")


@main.command()
@click.option("--path", default="semantic_cache.db", show_default=True, help="Path to the cache SQLite file.")
def purge(path: str) -> None:
    """Remove TTL-expired entries."""
    with SemanticCache(path=path) as cache:
        removed = cache.purge_expired()
        click.echo(f"purged {removed} expired entries")


@main.command()
@click.option("--path", default="semantic_cache.db", show_default=True, help="Path to the cache SQLite file.")
@click.option("--threshold", default=0.92, show_default=True, type=float, help="Similarity threshold.")
@click.argument("prompt")
def lookup(path: str, threshold: float, prompt: str) -> None:
    """Look up a prompt against the cache and print the result."""
    with SemanticCache(path=path, threshold=threshold) as cache:
        result = cache.get(prompt)
        if result.hit:
            click.echo(f"HIT (similarity={result.similarity:.3f}): {result.response}")
        else:
            click.echo(f"MISS (best similarity={result.similarity:.3f})")


if __name__ == "__main__":
    main()
