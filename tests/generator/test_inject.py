"""Injection sanity tests: every scenario labeled, premises hold, seeds reproduce.

Each injector gets a premise test verifying the injected events actually
constitute the attack its rule must detect — an injector whose premise is
broken silently destroys the recall measurement in Phase 3.
"""

from datetime import date, timedelta

import pytest

from ghostbadge.generator import (
    SCENARIOS,
    World,
    finalize_events,
    generate_benign_events,
    generate_roster,
    inject_scenarios,
    resolve_labels,
)
from ghostbadge.generator.org import DISTANT_CITIES
from ghostbadge.models import (
    BadgeDirection,
    BadgeResult,
    EmployeeStatus,
    Label,
    LoginType,
)

START = date(2026, 3, 2)
DAYS = 30
SEED = 42


def _build(seed: int = SEED) -> tuple[World, list[Label]]:
    roster = generate_roster(50, START, DAYS, seed=seed)
    badge, auth = generate_benign_events(roster, start_date=START, days=DAYS, seed=seed)
    world = World(roster=roster, badge=badge, auth=auth, start_date=START, days=DAYS)
    pending = inject_scenarios(world, sorted(SCENARIOS), seed=seed)
    finalize_events(world.badge, world.auth)
    return world, resolve_labels(pending)


@pytest.fixture(scope="module")
def injected() -> tuple[World, list[Label]]:
    return _build()


def _by_scenario(labels: list[Label], scenario: str) -> list[Label]:
    return [label for label in labels if label.scenario == scenario]


def _events_by_id(world: World) -> dict[str, object]:
    return {e.event_id: e for e in [*world.badge, *world.auth]}


def _badged_zones(world: World, employee_id: str, day: date) -> set[str]:
    return {
        e.zone
        for e in world.badge
        if e.employee_id == employee_id
        and e.ts.date() == day
        and e.direction is BadgeDirection.IN
        and e.result is BadgeResult.GRANTED
    }


def test_same_seed_reproduces_identical_labels(injected: tuple[World, list[Label]]) -> None:
    _, labels_a = injected
    _, labels_b = _build()
    assert [a.model_dump() for a in labels_a] == [b.model_dump() for b in labels_b]


def test_every_scenario_contributes_at_least_two_labels(
    injected: tuple[World, list[Label]],
) -> None:
    _, labels = injected
    for scenario in SCENARIOS:
        assert len(_by_scenario(labels, scenario)) >= 2, scenario


def test_labels_reference_real_events(injected: tuple[World, list[Label]]) -> None:
    world, labels = injected
    events = _events_by_id(world)
    roster_ids = {e.employee_id for e in world.roster}
    for label in labels:
        assert label.employee_id in roster_ids
        assert label.event_ids
        for event_id in label.event_ids:
            assert event_id in events, f"{label.scenario}: dangling {event_id}"


def test_benign_generation_yields_zero_labels() -> None:
    roster = generate_roster(50, START, DAYS, seed=SEED)
    badge, auth = generate_benign_events(roster, start_date=START, days=DAYS, seed=SEED)
    world = World(roster=roster, badge=badge, auth=auth, start_date=START, days=DAYS)
    assert inject_scenarios(world, [], seed=SEED) == []


def test_ghost_login_premise(injected: tuple[World, list[Label]]) -> None:
    """The account logs in on-site on a day its owner never badged in."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "ghost_login"):
        (login,) = (events[i] for i in label.event_ids)
        assert login.login_type is LoginType.INTERACTIVE
        assert not _badged_zones(world, label.employee_id, label.day)


def test_impossible_presence_premise(injected: tuple[World, list[Label]]) -> None:
    """Badge-in at HQ and a distant-geo VPN login within 45 minutes."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "impossible_presence"):
        badge_in, vpn = (events[i] for i in label.event_ids)
        assert badge_in.result is BadgeResult.GRANTED
        assert vpn.login_type is LoginType.VPN
        assert vpn.geo.city in DISTANT_CITIES
        assert timedelta(0) < vpn.ts - badge_in.ts < timedelta(minutes=45)


def test_zone_mismatch_premise(injected: tuple[World, list[Label]]) -> None:
    """Login zone was never badged into, though the employee badged elsewhere."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "zone_mismatch"):
        (login,) = (events[i] for i in label.event_ids)
        badged = _badged_zones(world, label.employee_id, label.day)
        assert badged, "employee should be present somewhere that day"
        assert login.host_zone not in badged


def test_after_hours_premise(injected: tuple[World, list[Label]]) -> None:
    """Dead-of-night badge-in followed by a sensitive-host login."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "after_hours"):
        evs = [events[i] for i in label.event_ids]
        badge_ins = [e for e in evs if hasattr(e, "direction")]
        logins = [e for e in evs if hasattr(e, "account")]
        assert len(badge_ins) == 2 and len(logins) == 1
        assert all(0 <= e.ts.hour < 4 for e in evs)
        assert logins[0].sensitive


def test_terminated_actor_premise(injected: tuple[World, list[Label]]) -> None:
    """Roster says terminated, yet labeled activity continues on/after term date."""
    world, labels = injected
    roster = {e.employee_id: e for e in world.roster}
    scenario_labels = _by_scenario(labels, "terminated_actor")
    for label in scenario_labels:
        emp = roster[label.employee_id]
        assert emp.status is EmployeeStatus.TERMINATED
        assert emp.term_date is not None and label.day >= emp.term_date
    # capped so leavers stay rare enough to look like an offboarding gap
    assert len({label.employee_id for label in scenario_labels}) <= 3


def test_tailgate_premise(injected: tuple[World, list[Label]]) -> None:
    """One swipe, two accounts logging in within 30s; tailgater has no swipe."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "tailgate"):
        swipe, a_login, b_login = (events[i] for i in label.event_ids)
        assert b_login.account == label.employee_id
        assert a_login.account != b_login.account
        assert a_login.host_zone == b_login.host_zone == swipe.zone
        for login in (a_login, b_login):
            assert timedelta(0) < login.ts - swipe.ts <= timedelta(seconds=30)
        assert swipe.zone not in _badged_zones(world, label.employee_id, label.day)


def test_credential_sharing_premise(injected: tuple[World, list[Label]]) -> None:
    """Same account in two zones minutes apart, badge trail covering only one."""
    world, labels = injected
    events = _events_by_id(world)
    for label in _by_scenario(labels, "credential_sharing"):
        first, second = (events[i] for i in label.event_ids)
        assert first.account == second.account == label.employee_id
        assert first.host_zone != second.host_zone
        assert timedelta(minutes=3) < second.ts - first.ts < timedelta(minutes=7)
        assert second.host_zone not in _badged_zones(world, label.employee_id, label.day)
