"""Roster generator sanity tests: determinism, validity, and CSV stability."""

import hashlib
from datetime import date, timedelta
from pathlib import Path

from ghostbadge.generator import generate_roster, write_roster_csv
from ghostbadge.generator.org import DEPARTMENTS, LOBBY
from ghostbadge.models import EmployeeStatus

START = date(2026, 3, 2)
DAYS = 30


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_reproduces_byte_identical_csv(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_roster_csv(generate_roster(50, START, DAYS, seed=42), a)
    write_roster_csv(generate_roster(50, START, DAYS, seed=42), b)
    assert _sha256(a) == _sha256(b)


def test_different_seed_changes_output(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_roster_csv(generate_roster(50, START, DAYS, seed=42), a)
    write_roster_csv(generate_roster(50, START, DAYS, seed=43), b)
    assert _sha256(a) != _sha256(b)


def test_roster_validity() -> None:
    roster = generate_roster(50, START, DAYS, seed=42)

    assert len(roster) == 50
    ids = [e.employee_id for e in roster]
    assert len(set(ids)) == 50, "employee ids must be unique"
    names = [e.name for e in roster]
    assert len(set(names)) == 50, "names are sampled without replacement"

    for emp in roster:
        assert emp.department in DEPARTMENTS
        assert emp.permitted_zones[0] == LOBBY
        assert emp.home_zone in emp.permitted_zones
        if emp.status is EmployeeStatus.TERMINATED:
            assert emp.term_date is not None
            assert START <= emp.term_date <= START + timedelta(days=DAYS - 1)
        else:
            assert emp.term_date is None


def test_terminated_rate_is_plausible() -> None:
    # With a big roster the 5% termination rate should be visible but small.
    roster = generate_roster(400, START, DAYS, seed=7)
    n_term = sum(1 for e in roster if e.status is EmployeeStatus.TERMINATED)
    assert 0 < n_term < 400 * 0.15
