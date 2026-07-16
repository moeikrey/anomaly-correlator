"""Attack-scenario injection: surgical, labeled edits to the benign world.

The benign world is generated first and injectors modify it afterwards —
that keeps scenarios composable and the benign baseline reusable. Each
injector makes the smallest edit that produces its detection's signal
(usually adding 1-3 events) and returns pending labels for every instance;
`resolve_labels` turns those into ground-truth `Label` rows once event ids
exist. Rules are later scored against exactly these rows.

Injectors run in a fixed order and each re-derives its candidate pool from
the *current* (already partially injected) world, so e.g. ghost_login never
picks a day that after_hours just gave a badge trail.

Known cross-firing (deliberate, real attacks trip multiple wires): a
tailgater's login is also a zone mismatch; a shared credential appearing in
an unbadged zone likewise. Labels record only the scenario's primary rule —
Phase 3 scoring should treat an alert as a true positive when its evidence
overlaps any label's event_ids, and measure recall per rule_id_expected.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel

from ghostbadge.generator.events import _at, _emp_num, _vpn_ip, _workstation, _ws_ip
from ghostbadge.generator.org import DEPARTMENTS, DISTANT_CITIES
from ghostbadge.generator.rng import child_rng
from ghostbadge.models import (
    AuthEvent,
    BadgeDirection,
    BadgeEvent,
    BadgeResult,
    Employee,
    EmployeeStatus,
    GeoPoint,
    Label,
    LoginType,
)

Event = BadgeEvent | AuthEvent


class World(BaseModel):
    """The fully assembled synthetic dataset, mutable by injectors."""

    roster: list[Employee]
    badge: list[BadgeEvent]
    auth: list[AuthEvent]
    start_date: date
    days: int


@dataclass
class PendingLabel:
    """A label whose events don't have ids yet (ids arrive at finalization)."""

    scenario: str
    rule_id_expected: str
    employee_id: str
    day: date
    events: list[Event]


# --------------------------------------------------------------------------
# Candidate-pool helpers. All iterate roster/day order, never set order, so
# candidate lists (and therefore rng.sample results) are deterministic.
# --------------------------------------------------------------------------


def _window(world: World) -> list[date]:
    return [world.start_date + timedelta(days=i) for i in range(world.days)]


def _weekdays(world: World) -> list[date]:
    return [d for d in _window(world) if d.weekday() < 5]


def _active(world: World) -> list[Employee]:
    return [e for e in world.roster if e.status is EmployeeStatus.ACTIVE]


def _badge_map(world: World) -> dict[tuple[str, date], list[BadgeEvent]]:
    out: dict[tuple[str, date], list[BadgeEvent]] = {}
    for e in world.badge:
        out.setdefault((e.employee_id, e.ts.date()), []).append(e)
    return out


def _auth_map(world: World) -> dict[tuple[str, date], list[AuthEvent]]:
    out: dict[tuple[str, date], list[AuthEvent]] = {}
    for e in world.auth:
        out.setdefault((e.account, e.ts.date()), []).append(e)
    return out


def _zones_badged(events: list[BadgeEvent]) -> set[str]:
    return {
        e.zone
        for e in events
        if e.direction is BadgeDirection.IN and e.result is BadgeResult.GRANTED
    }


def _first_granted_in(events: list[BadgeEvent], zone: str | None = None) -> BadgeEvent | None:
    hits = [
        e
        for e in events
        if e.direction is BadgeDirection.IN
        and e.result is BadgeResult.GRANTED
        and (zone is None or e.zone == zone)
    ]
    return min(hits, key=lambda e: e.ts) if hits else None


def _residents(world: World, zone: str, exclude_id: str) -> list[Employee]:
    """Active employees whose own workstation lives in `zone`."""
    return [e for e in _active(world) if e.home_zone == zone and e.employee_id != exclude_id]


def _dept_zones() -> list[str]:
    return sorted({home for home, _ in DEPARTMENTS.values()})


def _take(rng: random.Random, candidates: list, count: int) -> list:
    return rng.sample(candidates, min(count, len(candidates)))


def _interactive(
    rng: random.Random, account: str, ts, host: str, zone: str, ip: str, *, sensitive=False
) -> AuthEvent:
    return AuthEvent(
        ts=ts.replace(microsecond=0),
        account=account,
        host=host,
        host_zone=zone,
        login_type=LoginType.INTERACTIVE,
        src_ip=ip,
        sensitive=sensitive,
    )


def _badge(emp_id: str, zone: str, ts, rng: random.Random) -> BadgeEvent:
    return BadgeEvent(
        ts=ts.replace(microsecond=0),
        employee_id=emp_id,
        door_id=f"D-{zone}-{rng.randint(1, 2)}",
        zone=zone,
        direction=BadgeDirection.IN,
        result=BadgeResult.GRANTED,
    )


# --------------------------------------------------------------------------
# Scenario injectors. Signature: (world, rng, count) -> list[PendingLabel].
# --------------------------------------------------------------------------


def inject_ghost_login(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-001: interactive login on-site while the account owner never badged in.

    The signature of stolen credentials used at the victim's own desk — the
    cyber log looks perfectly normal until you ask the badge system whether
    a body was present.
    """
    badge_map = _badge_map(world)
    candidates = [
        (emp, day)
        for emp in _active(world)
        for day in _weekdays(world)
        if (emp.employee_id, day) not in badge_map
    ]
    labels = []
    for emp, day in _take(rng, candidates, count):
        ts = _at(day, rng.uniform(540, 1020))  # business hours: nothing "off" but the ghost
        ev = _interactive(
            rng,
            emp.employee_id,
            ts,
            _workstation(emp),
            emp.home_zone,
            _ws_ip(emp.home_zone, _emp_num(emp)),
        )
        world.auth.append(ev)
        labels.append(PendingLabel("ghost_login", "GB-001", emp.employee_id, day, [ev]))
    return labels


def inject_impossible_presence(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-002: badged in at HQ, then a VPN login from >2000 km away within 45 min.

    One of the two authentications is not the employee. Physics is the
    detection: no traveler covers that distance inside the window.
    """
    badge_map = _badge_map(world)
    candidates = []
    for emp in _active(world):
        for day in _weekdays(world):
            first_in = _first_granted_in(badge_map.get((emp.employee_id, day), []))
            if first_in is not None:
                candidates.append((emp, day, first_in))
    labels = []
    for emp, day, first_in in _take(rng, candidates, count):
        city = rng.choice(sorted(DISTANT_CITIES))
        lat, lon = DISTANT_CITIES[city]
        ev = AuthEvent(
            ts=(first_in.ts + timedelta(minutes=rng.uniform(5, 44))).replace(microsecond=0),
            account=emp.employee_id,
            host="vpn-gw-1",
            host_zone=None,
            login_type=LoginType.VPN,
            src_ip=_vpn_ip(_emp_num(emp)),
            geo=GeoPoint(lat=lat, lon=lon, city=city),
        )
        world.auth.append(ev)
        labels.append(
            PendingLabel("impossible_presence", "GB-002", emp.employee_id, day, [first_in, ev])
        )
    return labels


def inject_zone_mismatch(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-003: login on a host in a zone the user never badged into that day.

    The badge trail says 3F-ENG; the auth log says a Sales-floor machine.
    Either credentials moved without the body, or someone piggybacked
    through a door the badge system never saw.
    """
    badge_map = _badge_map(world)
    candidates = []
    for emp in _active(world):
        for day in _weekdays(world):
            events = badge_map.get((emp.employee_id, day), [])
            first_in = _first_granted_in(events)
            if first_in is None:
                continue
            badged = _zones_badged(events)
            targets = [
                z
                for z in _dept_zones()
                if z not in badged and _residents(world, z, emp.employee_id)
            ]
            if targets:
                candidates.append((emp, day, first_in, targets))
    labels = []
    for emp, day, first_in, targets in _take(rng, candidates, count):
        zone = rng.choice(targets)
        owner = rng.choice(_residents(world, zone, emp.employee_id))
        ts = first_in.ts + timedelta(minutes=rng.uniform(60, 240))
        ev = _interactive(
            rng,
            emp.employee_id,
            ts,
            _workstation(owner),
            zone,
            _ws_ip(zone, _emp_num(owner)),
        )
        world.auth.append(ev)
        labels.append(PendingLabel("zone_mismatch", "GB-003", emp.employee_id, day, [ev]))
    return labels


def inject_after_hours(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-004: ~02:00 badge-in followed by access to a sensitive system.

    Individually explainable (people forget laptops; ops gets paged), but
    the *pairing* of a dead-of-night entry with crown-jewel access minutes
    later is how physical insiders exfiltrate.
    """
    candidates = [(emp, day) for emp in _active(world) for day in _window(world)]
    labels = []
    for emp, day in _take(rng, candidates, count):
        t0 = _at(day, rng.uniform(90, 180))  # 01:30-03:00 UTC
        b_lobby = _badge(emp.employee_id, "LOBBY", t0, rng)
        b_srv = _badge(
            emp.employee_id, "SRV-ROOM", t0 + timedelta(seconds=rng.randint(60, 150)), rng
        )
        login = _interactive(
            rng,
            emp.employee_id,
            b_srv.ts + timedelta(minutes=rng.uniform(8, 12)),
            f"SRV-{_emp_num(emp) % 5 + 1:02d}",
            "SRV-ROOM",
            _ws_ip("SRV-ROOM", _emp_num(emp)),
            sensitive=True,
        )
        world.badge.extend([b_lobby, b_srv])
        world.auth.append(login)
        labels.append(
            PendingLabel("after_hours", "GB-004", emp.employee_id, day, [b_lobby, b_srv, login])
        )
    return labels


def inject_terminated_actor(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-005: HR says terminated; badge and account activity continue anyway.

    Offboarding gaps are a classic insider hole — the badge deactivation
    ticket sits in a queue while the ex-employee's access keeps working.
    Implemented by back-dating an active employee's termination under their
    existing activity, so post-term events are already in both logs.
    """
    badge_map = _badge_map(world)
    auth_map = _auth_map(world)
    candidates = []
    for emp in _active(world):
        event_days = sorted(
            {day for (eid, day) in badge_map if eid == emp.employee_id}
            | {day for (acct, day) in auth_map if acct == emp.employee_id}
        )
        if len(event_days) >= 5:
            candidates.append((emp, event_days))
    labels = []
    for emp, event_days in _take(rng, candidates, count):
        cutoff = rng.randint(2, 4)  # leave 2-4 active days as the violation
        term = event_days[-cutoff]
        emp.status = EmployeeStatus.TERMINATED
        emp.term_date = term
        for day in event_days:
            if day < term:
                continue
            events: list[Event] = [
                *badge_map.get((emp.employee_id, day), []),
                *auth_map.get((emp.employee_id, day), []),
            ]
            labels.append(PendingLabel("terminated_actor", "GB-005", emp.employee_id, day, events))
    return labels


def inject_tailgate(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-006: one swipe at a zone door, two accounts logging in seconds later.

    Badge readers count cards, not people. The second account with no swipe
    of its own is the person who slipped through on someone else's badge.
    """
    badge_map = _badge_map(world)
    candidates = []
    for emp_a in _active(world):
        zone = emp_a.home_zone
        if not _residents(world, zone, emp_a.employee_id):
            continue
        for day in _weekdays(world):
            swipe = _first_granted_in(badge_map.get((emp_a.employee_id, day), []), zone)
            if swipe is None:
                continue
            tailgaters = [
                e
                for e in _active(world)
                if e.employee_id != emp_a.employee_id
                and (e.employee_id, day) in badge_map
                and zone not in _zones_badged(badge_map[(e.employee_id, day)])
            ]
            if tailgaters:
                candidates.append((emp_a, day, swipe, tailgaters))
    labels = []
    for emp_a, day, swipe, tailgaters in _take(rng, candidates, count):
        zone = emp_a.home_zone
        emp_b = rng.choice(tailgaters)
        host_owner = rng.choice(_residents(world, zone, emp_a.employee_id))
        a_login = _interactive(
            rng,
            emp_a.employee_id,
            swipe.ts + timedelta(seconds=rng.randint(5, 14)),
            _workstation(emp_a),
            zone,
            _ws_ip(zone, _emp_num(emp_a)),
        )
        b_login = _interactive(
            rng,
            emp_b.employee_id,
            swipe.ts + timedelta(seconds=rng.randint(15, 29)),
            _workstation(host_owner),
            zone,
            _ws_ip(zone, _emp_num(host_owner)),
        )
        world.auth.extend([a_login, b_login])
        labels.append(
            PendingLabel("tailgate", "GB-006", emp_b.employee_id, day, [swipe, a_login, b_login])
        )
    return labels


def inject_credential_sharing(world: World, rng: random.Random, count: int) -> list[PendingLabel]:
    """GB-007: one account active in two zones with no badge movement between.

    A password on a sticky note: the account owner works at their desk while
    a colleague (or thief) uses the same credentials across the building.
    """
    badge_map = _badge_map(world)
    auth_map = _auth_map(world)
    candidates = []
    for emp in _active(world):
        for day in _weekdays(world):
            logins = [
                e
                for e in auth_map.get((emp.employee_id, day), [])
                if e.login_type is LoginType.INTERACTIVE
            ]
            if not logins:
                continue
            badged = _zones_badged(badge_map.get((emp.employee_id, day), []))
            targets = [
                z
                for z in _dept_zones()
                if z not in badged and _residents(world, z, emp.employee_id)
            ]
            if targets:
                first_login = min(logins, key=lambda e: e.ts)
                candidates.append((emp, day, first_login, targets))
    labels = []
    for emp, day, first_login, targets in _take(rng, candidates, count):
        zone = rng.choice(targets)
        owner = rng.choice(_residents(world, zone, emp.employee_id))
        ev = _interactive(
            rng,
            emp.employee_id,
            first_login.ts + timedelta(minutes=rng.uniform(4, 6)),
            _workstation(owner),
            zone,
            _ws_ip(zone, _emp_num(owner)),
        )
        world.auth.append(ev)
        labels.append(
            PendingLabel("credential_sharing", "GB-007", emp.employee_id, day, [first_login, ev])
        )
    return labels


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

SCENARIOS = {
    "ghost_login": inject_ghost_login,
    "impossible_presence": inject_impossible_presence,
    "zone_mismatch": inject_zone_mismatch,
    "after_hours": inject_after_hours,
    "terminated_actor": inject_terminated_actor,
    "tailgate": inject_tailgate,
    "credential_sharing": inject_credential_sharing,
}

# Execution order matters: roster mutation first, badge-adding scenarios
# before badge-sensitive ones, and ghost_login last because its premise
# ("no badge events that day") must hold against the fully injected world.
_ORDER = [
    "terminated_actor",
    "after_hours",
    "tailgate",
    "credential_sharing",
    "zone_mismatch",
    "impossible_presence",
    "ghost_login",
]

DEFAULT_INJECT_RATE = 0.1  # scenario instances per employee-day, split evenly


def inject_scenarios(
    world: World,
    scenarios: list[str],
    seed: int,
    rate: float = DEFAULT_INJECT_RATE,
) -> list[PendingLabel]:
    """Apply the selected injectors to the benign world.

    Every scenario gets its own child RNG stream and at least 2 instances
    (so `ghostbadge score` always has positives to measure), except
    terminated_actor, which is capped at 3 employees — each one already
    yields several labeled post-termination days, and terminating a fifth
    of the company would stop looking like an offboarding gap.
    """
    unknown = sorted(set(scenarios) - set(SCENARIOS))
    if unknown:
        raise ValueError(f"unknown scenarios: {', '.join(unknown)}")
    if not scenarios:
        return []

    total = round(rate * len(world.roster) * world.days)
    per_scenario = max(2, total // len(scenarios))

    labels: list[PendingLabel] = []
    for name in _ORDER:
        if name not in scenarios:
            continue
        count = min(per_scenario, 3) if name == "terminated_actor" else per_scenario
        labels.extend(SCENARIOS[name](world, child_rng(seed, "inject", name), count))
    return labels


def resolve_labels(pending: list[PendingLabel]) -> list[Label]:
    """Convert pending labels to ground-truth rows (after finalize_events)."""
    labels = []
    for p in pending:
        ids = [e.event_id for e in p.events]
        if not ids or not all(ids):
            raise ValueError("resolve_labels must run after finalize_events assigns ids")
        labels.append(
            Label(
                scenario=p.scenario,
                rule_id_expected=p.rule_id_expected,
                employee_id=p.employee_id,
                event_ids=ids,
                day=p.day,
            )
        )
    labels.sort(key=lambda label: (label.day, label.scenario, label.employee_id))
    return labels
