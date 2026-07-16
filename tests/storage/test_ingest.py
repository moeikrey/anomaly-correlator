"""Ingestion tests: full-dataset load, malformed-row quarantine, UTC round-trip."""

import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from ghostbadge.storage import (
    AuthEventRow,
    BadgeEventRow,
    EmployeeRow,
    LabelRow,
    get_engine,
    ingest_dir,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "malformed"
START = date(2026, 3, 2)


def _write_dataset(out: Path) -> World:
    roster = generate_roster(12, START, 10, seed=7)
    badge, auth = generate_benign_events(roster, start_date=START, days=10, seed=7)
    world = World(roster=roster, badge=badge, auth=auth, start_date=START, days=10)
    pending = inject_scenarios(world, sorted(SCENARIOS), seed=7)
    finalize_events(world.badge, world.auth)
    labels = resolve_labels(pending)
    write_roster_csv(world.roster, out / "hr_roster.csv")
    write_jsonl(world.badge, out / "badge_events.jsonl")
    write_jsonl(world.auth, out / "auth_events.jsonl")
    write_jsonl(labels, out / "labels.jsonl")
    return world


def test_ingest_loads_generated_dataset_with_matching_counts(tmp_path: Path) -> None:
    world = _write_dataset(tmp_path)
    report = ingest_dir(tmp_path)

    assert report.total_rejected == 0
    assert report.employees.loaded == len(world.roster)
    assert report.badge_events.loaded == len(world.badge)
    assert report.auth_events.loaded == len(world.auth)
    assert report.labels.loaded > 0

    engine = get_engine(tmp_path / "ghostbadge.db")
    with Session(engine) as session:
        stored_badge = [r.to_model() for r in session.scalars(select(BadgeEventRow))]
        stored_auth = [r.to_model() for r in session.scalars(select(AuthEventRow))]
        stored_emps = [r.to_model() for r in session.scalars(select(EmployeeRow))]
        n_labels = len(session.scalars(select(LabelRow)).all())

    key = lambda e: e.event_id  # noqa: E731
    assert sorted(stored_badge, key=key) == sorted(world.badge, key=key)
    assert sorted(stored_auth, key=key) == sorted(world.auth, key=key)
    assert sorted(stored_emps, key=lambda e: e.employee_id) == world.roster
    assert n_labels == report.labels.loaded


def test_malformed_rows_are_skipped_with_warnings_not_crashes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="ghostbadge.ingest"):
        report = ingest_dir(FIXTURES, db_path=tmp_path / "test.db")

    # hr_roster: bad status enum + home_zone not permitted
    assert (report.employees.loaded, report.employees.rejected) == (2, 2)
    # badge: truncated JSON + naive timestamp + duplicate event_id
    assert (report.badge_events.loaded, report.badge_events.rejected) == (2, 3)
    # auth: vpn-with-host_zone + missing account (offset-ts row is *valid*)
    assert (report.auth_events.loaded, report.auth_events.rejected) == (2, 2)
    # labels: one good, one missing required fields
    assert (report.labels.loaded, report.labels.rejected) == (1, 1)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == report.total_rejected == 8
    assert all("rejected" in r.message for r in warnings)


def test_offset_timestamps_are_normalized_to_utc(tmp_path: Path) -> None:
    """The +02:00 fixture row must come back as an aware UTC instant."""
    ingest_dir(FIXTURES, db_path=tmp_path / "test.db")
    engine = get_engine(tmp_path / "test.db")
    with Session(engine) as session:
        row = session.get(AuthEventRow, "a-000002")
        model = row.to_model()
    assert model.ts == datetime(2026, 3, 2, 10, 15, tzinfo=UTC)
    assert model.ts.utcoffset().total_seconds() == 0


def test_missing_required_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_dir(tmp_path)
