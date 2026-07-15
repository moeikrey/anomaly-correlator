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
    """Generate the synthetic world (currently: HR roster; events follow)."""
    from ghostbadge.generator import generate_roster, write_roster_csv
    from ghostbadge.models import EmployeeStatus

    roster = generate_roster(
        n_employees=employees,
        start_date=date.fromisoformat(start_date),
        days=days,
        seed=seed,
    )
    roster_path = out / "hr_roster.csv"
    write_roster_csv(roster, roster_path)

    n_term = sum(1 for e in roster if e.status is EmployeeStatus.TERMINATED)
    typer.echo(f"wrote {roster_path} ({len(roster)} employees, {n_term} terminated in window)")
