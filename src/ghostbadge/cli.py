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
def ingest(
    data_dir: Path = typer.Argument(
        Path("data"), exists=True, file_okay=False, help="Directory with generated dataset."
    ),
    db: Path | None = typer.Option(
        None, help="SQLite output path (default: <data-dir>/ghostbadge.db)."
    ),
) -> None:
    """Validate a dataset directory and load it into SQLite."""
    import logging

    from ghostbadge.storage import ingest_dir

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    report = ingest_dir(data_dir, db)

    db_path = db or data_dir / "ghostbadge.db"
    for stream in ("employees", "badge_events", "auth_events", "labels"):
        counts = getattr(report, stream)
        typer.echo(f"{stream}: {counts.loaded} loaded, {counts.rejected} rejected")
    typer.echo(f"db: {db_path}")
    if report.total_rejected:
        typer.echo(f"warning: {report.total_rejected} malformed rows skipped (see log above)")


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
    inject: str = typer.Option(
        "",
        help="Comma-separated attack scenarios to inject, or 'all'. Empty = benign only.",
    ),
    inject_rate: float = typer.Option(
        0.1, help="Injected scenario instances per employee-day, split across scenarios."
    ),
    out: Path = typer.Option(Path("data"), help="Output directory."),
) -> None:
    """Generate the synthetic world: roster, events, and ground-truth labels."""
    from ghostbadge.generator import (
        SCENARIOS,
        World,
        finalize_events,
        generate_benign_events,
        generate_roster,
        inject_scenarios,
        resolve_labels,
        write_jsonl,
        write_roster_csv,
    )
    from ghostbadge.models import EmployeeStatus

    names = [s.strip() for s in inject.split(",") if s.strip()]
    if names == ["all"]:
        names = sorted(SCENARIOS)
    unknown = sorted(set(names) - set(SCENARIOS))
    if unknown:
        raise typer.BadParameter(
            f"unknown scenarios: {', '.join(unknown)} (available: {', '.join(sorted(SCENARIOS))})"
        )

    start = date.fromisoformat(start_date)
    roster = generate_roster(n_employees=employees, start_date=start, days=days, seed=seed)
    badge, auth = generate_benign_events(roster, start_date=start, days=days, seed=seed)
    world = World(roster=roster, badge=badge, auth=auth, start_date=start, days=days)
    pending = inject_scenarios(world, names, seed=seed, rate=inject_rate)
    finalize_events(world.badge, world.auth)
    labels = resolve_labels(pending)

    roster_path = out / "hr_roster.csv"
    write_roster_csv(world.roster, roster_path)
    write_jsonl(world.badge, out / "badge_events.jsonl")
    write_jsonl(world.auth, out / "auth_events.jsonl")
    write_jsonl(labels, out / "labels.jsonl")

    n_term = sum(1 for e in world.roster if e.status is EmployeeStatus.TERMINATED)
    typer.echo(f"wrote {roster_path} ({len(world.roster)} employees, {n_term} terminated)")
    typer.echo(f"wrote {out / 'badge_events.jsonl'} ({len(world.badge)} events)")
    typer.echo(f"wrote {out / 'auth_events.jsonl'} ({len(world.auth)} events)")
    scenario_counts = sorted({label.scenario for label in labels})
    typer.echo(
        f"wrote {out / 'labels.jsonl'} ({len(labels)} labels"
        + (f" across {len(scenario_counts)} scenarios)" if labels else ", benign world)")
    )
