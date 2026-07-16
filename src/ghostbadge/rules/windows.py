"""Day windows: the pre-indexed view of one calendar day that rules consume.

Rules are pure functions over these windows — no DB handles, no clocks, no
I/O — which is what makes every detection unit-testable from hand-built
fixtures and every alert reproducible from stored events. The full roster
rides along in every window because the roster is the bridge between the
physical and cyber worlds (status, term dates, permitted zones), and
"employee absent from roster" must stay distinguishable from "employee
present but inactive".
"""

from datetime import date

from pydantic import BaseModel

from ghostbadge.models import AuthEvent, BadgeEvent, Employee


class DayWindow(BaseModel):
    """All events for one UTC calendar day, indexed by employee/account."""

    day: date
    employees: dict[str, Employee]
    badge_by_employee: dict[str, list[BadgeEvent]]
    auth_by_account: dict[str, list[AuthEvent]]


def build_day_windows(
    roster: list[Employee],
    badge: list[BadgeEvent],
    auth: list[AuthEvent],
) -> list[DayWindow]:
    """Group event streams into per-day windows (sorted by day, then ts)."""
    employees = {e.employee_id: e for e in roster}
    badge_days: dict[date, dict[str, list[BadgeEvent]]] = {}
    for event in sorted(badge, key=lambda e: e.ts):
        badge_days.setdefault(event.ts.date(), {}).setdefault(event.employee_id, []).append(event)
    auth_days: dict[date, dict[str, list[AuthEvent]]] = {}
    for event in sorted(auth, key=lambda e: e.ts):
        auth_days.setdefault(event.ts.date(), {}).setdefault(event.account, []).append(event)

    return [
        DayWindow(
            day=day,
            employees=employees,
            badge_by_employee=badge_days.get(day, {}),
            auth_by_account=auth_days.get(day, {}),
        )
        for day in sorted(badge_days.keys() | auth_days.keys())
    ]
