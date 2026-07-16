"""Benign-world sanity tests: determinism, causality, and deliberate mess.

These encode the synthetic-data golden rules: badge-ins precede logins,
remote days have no badge trail, terminated employees go quiet, and a fixed
seed reproduces byte-identical files.
"""

import hashlib
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

from ghostbadge.generator import (
    finalize_events,
    generate_benign_events,
    generate_roster,
    write_jsonl,
)
from ghostbadge.models import (
    AuthEvent,
    BadgeDirection,
    BadgeEvent,
    BadgeResult,
    Employee,
    LoginType,
)

START = date(2026, 3, 2)
DAYS = 30
SEED = 42


def _build(seed: int = SEED) -> tuple[list[Employee], list[BadgeEvent], list[AuthEvent]]:
    roster = generate_roster(50, START, DAYS, seed=seed)
    badge, auth = generate_benign_events(roster, start_date=START, days=DAYS, seed=seed)
    finalize_events(badge, auth)
    return roster, badge, auth


@pytest.fixture(scope="module")
def world() -> tuple[list[Employee], list[BadgeEvent], list[AuthEvent]]:
    return _build()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_reproduces_byte_identical_files(
    tmp_path: Path, world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]]
) -> None:
    _, badge_a, auth_a = world
    _, badge_b, auth_b = _build()
    write_jsonl(badge_a, tmp_path / "badge_a.jsonl")
    write_jsonl(badge_b, tmp_path / "badge_b.jsonl")
    write_jsonl(auth_a, tmp_path / "auth_a.jsonl")
    write_jsonl(auth_b, tmp_path / "auth_b.jsonl")
    assert _sha256(tmp_path / "badge_a.jsonl") == _sha256(tmp_path / "badge_b.jsonl")
    assert _sha256(tmp_path / "auth_a.jsonl") == _sha256(tmp_path / "auth_b.jsonl")


def test_referential_integrity(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    roster, badge, auth = world
    ids = {e.employee_id for e in roster}
    assert {e.employee_id for e in badge} <= ids
    assert {e.account for e in auth} <= ids


def test_streams_sorted_with_sequential_ids(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    _, badge, auth = world
    assert [e.ts for e in badge] == sorted(e.ts for e in badge)
    assert [e.ts for e in auth] == sorted(e.ts for e in auth)
    assert [e.event_id for e in badge] == [f"b-{i + 1:06d}" for i in range(len(badge))]
    assert [e.event_id for e in auth] == [f"a-{i + 1:06d}" for i in range(len(auth))]


def test_badge_in_precedes_interactive_logins(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    """Causality even under clock skew: no benign ghost logins (GB-001)."""
    _, badge, auth = world
    first_badge_in: dict[tuple[str, date], object] = {}
    for e in badge:
        if e.direction is BadgeDirection.IN and e.result is BadgeResult.GRANTED:
            key = (e.employee_id, e.ts.date())
            if key not in first_badge_in or e.ts < first_badge_in[key]:
                first_badge_in[key] = e.ts

    for e in auth:
        if e.login_type is LoginType.INTERACTIVE:
            key = (e.account, e.ts.date())
            assert key in first_badge_in, f"login without any badge-in: {e.event_id}"
            assert e.ts > first_badge_in[key], f"login precedes badge-in: {e.event_id}"


def test_login_zones_were_badged_into(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    """No benign zone mismatches (GB-003): people log in where they badged."""
    _, badge, auth = world
    zones_by_day: dict[tuple[str, date], set[str]] = defaultdict(set)
    for e in badge:
        if e.direction is BadgeDirection.IN and e.result is BadgeResult.GRANTED:
            zones_by_day[(e.employee_id, e.ts.date())].add(e.zone)

    for e in auth:
        if e.login_type is LoginType.INTERACTIVE:
            assert e.host_zone in zones_by_day[(e.account, e.ts.date())]


def test_vpn_days_have_no_badge_events(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    _, badge, auth = world
    badge_days = {(e.employee_id, e.ts.date()) for e in badge}
    vpn_events = [e for e in auth if e.login_type is LoginType.VPN]
    assert vpn_events, "benign world should contain remote days"
    for e in vpn_events:
        assert e.geo is not None
        assert e.host_zone is None
        assert (e.account, e.ts.date()) not in badge_days


def test_terminated_employees_go_quiet(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    roster, badge, auth = world
    term = {e.employee_id: e.term_date for e in roster if e.term_date is not None}
    assert term, "roster should contain leavers"
    for e in badge:
        if e.employee_id in term:
            assert e.ts.date() < term[e.employee_id]
    for e in auth:
        if e.account in term:
            assert e.ts.date() < term[e.account]


def test_deliberate_mess_is_present_but_rare(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    _, badge, _ = world
    denied = [e for e in badge if e.result is BadgeResult.DENIED]
    assert denied, "real logs contain denied reads"
    assert len(denied) / len(badge) < 0.05

    # Some office days must lack a badge-out (exits are less enforced).
    days_with_in = {(e.employee_id, e.ts.date()) for e in badge if e.direction is BadgeDirection.IN}
    days_with_out = {
        (e.employee_id, e.ts.date()) for e in badge if e.direction is BadgeDirection.OUT
    }
    assert days_with_in - days_with_out, "some days should be missing a badge-out"


def test_volume_is_plausible(
    world: tuple[list[Employee], list[BadgeEvent], list[AuthEvent]],
) -> None:
    """~50 employees x 30 days should produce a demo-sized, non-trivial world."""
    _, badge, auth = world
    assert 1_000 < len(badge) < 20_000
    assert 500 < len(auth) < 10_000
