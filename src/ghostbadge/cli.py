"""Typer CLI entry point.

Subcommands (generate, ingest, run, score, report) are added phase by phase;
this stub exists so the `ghostbadge` console script is valid from Phase 0.
"""

import typer

app = typer.Typer(
    name="ghostbadge",
    help="Correlate badge-access and network-auth logs to detect anomalies.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Correlate badge-access and network-auth logs to detect anomalies."""


@app.command()
def version() -> None:
    """Print the installed GhostBadge version."""
    from ghostbadge import __version__

    typer.echo(f"ghostbadge {__version__}")
