"""Typer CLI entry point.

Subcommands (generate, ingest, run, score, report) are added phase by phase;
this stub exists so the `ghostbadge` console script is valid from Phase 0.
"""

from datetime import date
from pathlib import Path

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


@app.command()
def generate(
    employees: int = typer.Option(50, min=1, help="Number of synthetic employees."),
    days: int = typer.Option(30, min=1, help="Length of the simulation window."),
    seed: int = typer.Option(42, help="Master seed; same seed -> identical output."),
    start_date: str = typer.Option(
        "2026-03-02", help="First day of the window (ISO date, a fixed default)."
    ),
    out: Path = typer.Option(Path("data"), help="Output directory."),
) -> None:
    """Generate the synthetic world (roster + benign events; injection follows)."""
    from ghostbadge.generator import (
        finalize_events,
        generate_benign_events,
        generate_roster,
        write_events_jsonl,
        write_roster_csv,
    )
    from ghostbadge.models import EmployeeStatus

    start = date.fromisoformat(start_date)
    roster = generate_roster(n_employees=employees, start_date=start, days=days, seed=seed)
    badge, auth = generate_benign_events(roster, start_date=start, days=days, seed=seed)
    finalize_events(badge, auth)

    roster_path = out / "hr_roster.csv"
    write_roster_csv(roster, roster_path)
    write_events_jsonl(badge, out / "badge_events.jsonl")
    write_events_jsonl(auth, out / "auth_events.jsonl")

    n_term = sum(1 for e in roster if e.status is EmployeeStatus.TERMINATED)
    typer.echo(f"wrote {roster_path} ({len(roster)} employees, {n_term} terminated in window)")
    typer.echo(f"wrote {out / 'badge_events.jsonl'} ({len(badge)} events)")
    typer.echo(f"wrote {out / 'auth_events.jsonl'} ({len(auth)} events)")
