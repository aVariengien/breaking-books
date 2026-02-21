#!/usr/bin/env python3
"""
CLI tool for managing API cache.
"""

import typer

from api_cache import CACHE_DIR, DISABLE_CACHE, clear_cache, get_cache_stats

app = typer.Typer(help="Manage API response cache")


@app.command()
def stats():
    """Show cache statistics."""
    if DISABLE_CACHE:
        typer.echo("🚫 Cache is disabled (DISABLE_API_CACHE=true)")
        return

    stats = get_cache_stats()
    typer.echo("📊 Cache Statistics:")
    typer.echo(f"   Location: {CACHE_DIR}")
    typer.echo(f"   Total cached responses: {stats['total_cached']}")
    typer.echo(f"   AI completions: {stats['completions']}")
    typer.echo(f"   Images: {stats['images']}")


@app.command()
def clear():
    """Clear all cached responses."""
    if DISABLE_CACHE:
        typer.echo("🚫 Cache is disabled (DISABLE_API_CACHE=true)")
        return

    confirm = typer.confirm("Are you sure you want to clear all cached API responses?")
    if confirm:
        clear_cache()
    else:
        typer.echo("❌ Cache clear cancelled")


@app.command()
def location():
    """Show cache directory location."""
    typer.echo(f"📁 Cache directory: {CACHE_DIR.absolute()}")
    if DISABLE_CACHE:
        typer.echo("🚫 Cache is currently disabled (DISABLE_API_CACHE=true)")


if __name__ == "__main__":
    app()
