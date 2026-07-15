"""HR roster generation.

The roster anchors every other synthetic artifact: badge and auth events are
generated *per employee* from it, and the terminated-actor detection (GB-005)
is only as good as the status/term_date fields here. A small fraction of
employees is terminated mid-window even in the benign world — real rosters
always contain leavers, and a detector that has never seen a *quiet* leaver
(terminated, then correctly silent) is untested against its main false-positive
source.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from ghostbadge.generator.org import (
    DEPARTMENT_WEIGHTS,
    DEPARTMENTS,
    FIRST_NAMES,
    LAST_NAMES,
    LOBBY,
)
from ghostbadge.generator.rng import child_rng
from ghostbadge.models import Employee, EmployeeStatus

# Roughly 1 in 20 employees leaves during a 30-day window; enough to exercise
# term-date handling without making departures look like an incident.
TERMINATED_RATE = 0.05

ROSTER_FIELDS = [
    "employee_id",
    "name",
    "department",
    "home_zone",
    "permitted_zones",
    "status",
    "term_date",
]


def generate_roster(
    n_employees: int,
    start_date: date,
    days: int,
    seed: int,
) -> list[Employee]:
    """Generate a deterministic synthetic HR roster.

    Draws only from the ``roster`` child stream of the master seed, so the
    same (n_employees, start_date, days, seed) always yields the identical
    roster regardless of what else the generator produces.
    """
    rng = child_rng(seed, "roster")

    full_names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    names = rng.sample(full_names, n_employees)

    dept_names = list(DEPARTMENTS)
    weights = [DEPARTMENT_WEIGHTS[d] for d in dept_names]

    employees: list[Employee] = []
    for i in range(n_employees):
        department = rng.choices(dept_names, weights=weights, k=1)[0]
        home_zone, extra_zones = DEPARTMENTS[department]

        terminated = rng.random() < TERMINATED_RATE
        term_date = start_date + timedelta(days=rng.randrange(days)) if terminated else None

        employees.append(
            Employee(
                employee_id=f"E{i + 1:03d}",
                name=names[i],
                department=department,
                home_zone=home_zone,
                permitted_zones=[LOBBY, home_zone, *extra_zones],
                status=(EmployeeStatus.TERMINATED if terminated else EmployeeStatus.ACTIVE),
                term_date=term_date,
            )
        )
    return employees


def write_roster_csv(employees: list[Employee], path: Path) -> None:
    """Write the roster as CSV with a stable field order and LF line endings.

    Output must be byte-identical for a fixed seed (tests hash it), so
    everything that could vary is pinned: field order, list separator,
    ISO term dates, and the line terminator.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ROSTER_FIELDS, lineterminator="\n")
        writer.writeheader()
        for emp in employees:
            writer.writerow(
                {
                    "employee_id": emp.employee_id,
                    "name": emp.name,
                    "department": emp.department,
                    "home_zone": emp.home_zone,
                    "permitted_zones": ";".join(emp.permitted_zones),
                    "status": emp.status.value,
                    "term_date": emp.term_date.isoformat() if emp.term_date else "",
                }
            )
