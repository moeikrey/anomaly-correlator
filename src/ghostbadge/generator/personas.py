"""Per-employee behavioral personas.

Realistic benign data needs *stable habits*: the same person arrives around
the same time every day, favors the same zones, and works remotely at a
personal rate. Without personas, every day would be an independent random
draw and normal behavior would look anomalous everywhere — drowning the
detections we're trying to showcase. Each persona is sampled once from its
own child RNG stream (keyed by employee id), so rosters and narratives can
change without reshuffling anyone's personality.
"""

from pydantic import BaseModel

from ghostbadge.generator.org import BENIGN_CITIES, LOBBY
from ghostbadge.generator.rng import child_rng
from ghostbadge.models import Employee, GeoPoint

# Department-typical arrival times, minutes after midnight UTC (the synthetic
# office runs on UTC so rules never juggle offsets). Ops/facilities start
# early; engineers drift in late. Spread matters: uniform arrivals would make
# after-hours (GB-004) baselines unrealistically clean.
DEPT_ARRIVAL_MEAN_MIN: dict[str, int] = {
    "Engineering": 570,  # 09:30
    "Sales": 510,  # 08:30
    "IT Operations": 480,  # 08:00
    "Finance": 510,  # 08:30
    "Executive": 540,  # 09:00
    "Facilities": 450,  # 07:30
}


class Persona(BaseModel):
    """Stable behavioral traits for one employee, sampled once per seed."""

    employee_id: str
    arrival_mean_min: float  # personal mean arrival, minutes after 00:00 UTC
    lunch_prob: float  # chance of a badge-out/in pair around noon
    remote_prob: float  # chance a given weekday is a VPN-from-home day
    visit_zones: list[str]  # 0-2 permitted zones they sometimes wander to
    home_geo: GeoPoint  # city their benign VPN logins originate from


def build_persona(employee: Employee, seed: int) -> Persona:
    """Sample an employee's persona from their own child RNG stream."""
    rng = child_rng(seed, "persona", employee.employee_id)

    base = DEPT_ARRIVAL_MEAN_MIN[employee.department]
    candidates = [z for z in employee.permitted_zones if z not in (LOBBY, employee.home_zone)]
    n_visits = min(len(candidates), rng.randint(0, 2))

    city = rng.choice(sorted(BENIGN_CITIES))
    lat, lon = BENIGN_CITIES[city]

    return Persona(
        employee_id=employee.employee_id,
        arrival_mean_min=base + rng.uniform(-30, 30),
        lunch_prob=rng.uniform(0.3, 0.5),
        remote_prob=rng.uniform(0.10, 0.20),
        visit_zones=rng.sample(candidates, k=n_visits),
        home_geo=GeoPoint(lat=lat, lon=lon, city=city),
    )
