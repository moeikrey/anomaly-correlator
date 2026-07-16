"""Hand-crafted fixture factories for rule tests.

Rule tests use minimal, explicit event sets — never full generator runs —
so each test reads as the scenario it encodes.
"""

from datetime import UTC, date, datetime

from ghostbadge.models import AuthEvent, BadgeEvent, Employee, GeoPoint
from ghostbadge.rules import DayWindow, build_day_windows

DAY = date(2026, 3, 2)


def ts(hour: int, minute: int = 0, second: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


def emp(employee_id: str = "E001", home_zone: str = "3F-ENG", **kw) -> Employee:
    defaults = {
        "name": f"Fixture {employee_id}",
        "department": "Engineering",
        "home_zone": home_zone,
        "permitted_zones": ["LOBBY", home_zone],
        "status": "active",
    }
    return Employee(employee_id=employee_id, **{**defaults, **kw})


def badge(
    event_id: str, employee_id: str, when: datetime, zone: str = "3F-ENG", **kw
) -> BadgeEvent:
    defaults = {"door_id": f"D-{zone}-1", "direction": "in", "result": "granted"}
    return BadgeEvent(
        event_id=event_id, ts=when, employee_id=employee_id, zone=zone, **{**defaults, **kw}
    )


def login(
    event_id: str, account: str, when: datetime, zone: str | None = "3F-ENG", **kw
) -> AuthEvent:
    defaults = {
        "host": f"WS-{zone}-001" if zone else "vpn-gw-1",
        "host_zone": zone,
        "login_type": "interactive" if zone else "vpn",
        "src_ip": "10.4.0.11",
        "geo": None if zone else GeoPoint(lat=37.77, lon=-122.42, city="San Francisco"),
    }
    return AuthEvent(event_id=event_id, ts=when, account=account, **{**defaults, **kw})


def window(
    employees: list[Employee],
    badge_events: list[BadgeEvent] = (),
    auth_events: list[AuthEvent] = (),
    day: date = DAY,
) -> DayWindow:
    windows = build_day_windows(employees, list(badge_events), list(auth_events))
    for w in windows:
        if w.day == day:
            return w
    return DayWindow(
        day=day,
        employees={e.employee_id: e for e in employees},
        badge_by_employee={},
        auth_by_account={},
    )
