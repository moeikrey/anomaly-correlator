"""Benign badge/auth event generation: each employee-day is one narrative.

Golden rule of the synthetic world: in benign data, physical events *cause*
cyber events. An employee badges into the lobby, then their home zone, then
logs into their own workstation minutes later; VPN days have no badge events
at all. Generating each day as a coherent story (instead of independent event
streams) is what makes the correlations detectable — and makes injected
attacks stand out as *broken causality* rather than just extra noise.

Deliberate imperfections (denied reads, missing badge-outs, auth clock skew)
are included because real logs are messy; a detector tuned on sterile data
false-positives the moment it sees reality.
"""

from datetime import UTC, date, datetime, time, timedelta

from ghostbadge.generator.org import ZONES
from ghostbadge.generator.personas import Persona, build_persona
from ghostbadge.generator.rng import child_rng
from ghostbadge.models import (
    AuthEvent,
    BadgeDirection,
    BadgeEvent,
    BadgeResult,
    Employee,
    LoginType,
)

# Behavior-model knobs (probabilities per employee-day unless noted).
WEEKEND_VISIT_PROB = 0.05  # honest after-hours noise so GB-004 isn't trivial
MISSING_BADGE_OUT_PROB = 0.08  # exits are less enforced; people tailgate out
DENIED_RETRY_PROB = 0.01  # per granted badge-in: a denied read precedes it
ZONE_VISIT_PROB = 0.30  # persona with visit zones actually wanders today
SRV_LOGIN_PROB = 0.70  # a SRV-ROOM visit includes a sensitive-host login
CLOCK_SKEW_S = 90  # auth timestamps jitter vs. the badge system's clock
# Badge-in must lead its first login by more than the max skew, or jitter
# could invert cause and effect and poison the GB-001/GB-003 baselines.
MIN_BADGE_TO_LOGIN_MIN = 3


def _at(day: date, minutes: float) -> datetime:
    """Timestamp `minutes` after midnight UTC on `day`, second precision."""
    base = datetime.combine(day, time(tzinfo=UTC))
    return (base + timedelta(minutes=minutes)).replace(microsecond=0)


def _emp_num(employee: Employee) -> int:
    return int(employee.employee_id[1:])


def _ws_ip(zone: str, n: int) -> str:
    """RFC1918 workstation address: one /16 per zone, host part from emp #."""
    return f"10.{ZONES.index(zone) + 1}.{n // 200}.{n % 200 + 10}"


def _vpn_ip(n: int) -> str:
    """RFC1918 VPN client pool address, stable per employee."""
    return f"172.16.{n // 200}.{n % 200 + 10}"


class _DayWriter:
    """Accumulates one employee-day's events with the mess baked in."""

    def __init__(
        self,
        employee: Employee,
        rng,
        badge_out: list[BadgeEvent],
        auth_out: list[AuthEvent],
    ) -> None:
        self.emp = employee
        self.rng = rng
        self.badge = badge_out
        self.auth = auth_out

    def badge_event(self, zone: str, direction: BadgeDirection, ts: datetime) -> None:
        ts = ts.replace(microsecond=0)  # all event streams are second-precision
        door = f"D-{zone}-{self.rng.randint(1, 2)}"
        if direction is BadgeDirection.IN and self.rng.random() < DENIED_RETRY_PROB:
            self.badge.append(
                BadgeEvent(
                    ts=ts - timedelta(seconds=self.rng.randint(20, 40)),
                    employee_id=self.emp.employee_id,
                    door_id=door,
                    zone=zone,
                    direction=direction,
                    result=BadgeResult.DENIED,
                )
            )
        self.badge.append(
            BadgeEvent(
                ts=ts,
                employee_id=self.emp.employee_id,
                door_id=door,
                zone=zone,
                direction=direction,
                result=BadgeResult.GRANTED,
            )
        )

    def login(
        self,
        ts: datetime,
        host: str,
        host_zone: str,
        *,
        sensitive: bool = False,
    ) -> None:
        skew = timedelta(seconds=self.rng.uniform(-CLOCK_SKEW_S, CLOCK_SKEW_S))
        self.auth.append(
            AuthEvent(
                ts=(ts + skew).replace(microsecond=0),
                account=self.emp.employee_id,
                host=host,
                host_zone=host_zone,
                login_type=LoginType.INTERACTIVE,
                src_ip=_ws_ip(host_zone, _emp_num(self.emp)),
                sensitive=sensitive,
            )
        )

    def vpn_login(self, ts: datetime, persona: Persona) -> None:
        self.auth.append(
            AuthEvent(
                ts=ts.replace(microsecond=0),
                account=self.emp.employee_id,
                host="vpn-gw-1",
                host_zone=None,
                login_type=LoginType.VPN,
                src_ip=_vpn_ip(_emp_num(self.emp)),
                geo=persona.home_geo,
            )
        )


def generate_benign_events(
    roster: list[Employee],
    start_date: date,
    days: int,
    seed: int,
) -> tuple[list[BadgeEvent], list[AuthEvent]]:
    """Generate the fully benign world for every employee-day in the window.

    Each (employee, day) draws from its own child RNG stream, so injectors
    and future behavior tweaks can't reshuffle unrelated days. Terminated
    employees go quiet on their term date — the benign world must contain
    honest leavers who *don't* trigger GB-005.
    """
    badge: list[BadgeEvent] = []
    auth: list[AuthEvent] = []

    for emp in roster:
        persona = build_persona(emp, seed)
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            if emp.term_date is not None and day >= emp.term_date:
                continue
            rng = child_rng(seed, "narrative", emp.employee_id, day.isoformat())
            writer = _DayWriter(emp, rng, badge, auth)
            if day.weekday() >= 5:
                _weekend_day(writer, rng, emp, day)
            elif rng.random() < persona.remote_prob:
                _remote_day(writer, rng, persona, day)
            else:
                _office_day(writer, rng, emp, persona, day)

    return badge, auth


def _remote_day(writer: _DayWriter, rng, persona: Persona, day: date) -> None:
    """VPN from the persona's home city; crucially, zero badge events."""
    times = sorted(rng.uniform(510, 1020) for _ in range(rng.randint(1, 2)))
    for minutes in times:
        writer.vpn_login(_at(day, minutes), persona)


def _weekend_day(writer: _DayWriter, rng, emp: Employee, day: date) -> None:
    """Rare legitimate weekend visit: badge trail intact, short stay."""
    if rng.random() >= WEEKEND_VISIT_PROB:
        return
    start = rng.uniform(540, 960)  # 09:00-16:00
    duration = rng.uniform(60, 120)

    t_lobby = _at(day, start)
    writer.badge_event("LOBBY", BadgeDirection.IN, t_lobby)
    t_home = t_lobby + timedelta(seconds=rng.randint(45, 180))
    writer.badge_event(emp.home_zone, BadgeDirection.IN, t_home)

    if rng.random() < 0.7:
        t_login = t_home + timedelta(minutes=rng.uniform(MIN_BADGE_TO_LOGIN_MIN, 10))
        writer.login(t_login, _workstation(emp), emp.home_zone)

    if rng.random() >= MISSING_BADGE_OUT_PROB:
        writer.badge_event("LOBBY", BadgeDirection.OUT, _at(day, start + duration))


def _office_day(writer: _DayWriter, rng, emp: Employee, persona: Persona, day: date) -> None:
    """The standard narrative: arrive, log in, maybe lunch/wander, leave."""
    arrival = min(max(rng.normalvariate(persona.arrival_mean_min, 20), 300), 720)
    workday = min(max(rng.normalvariate(510, 45), 360), 660)
    departure = arrival + workday

    t_lobby = _at(day, arrival)
    writer.badge_event("LOBBY", BadgeDirection.IN, t_lobby)
    t_home = t_lobby + timedelta(seconds=rng.randint(45, 180))
    writer.badge_event(emp.home_zone, BadgeDirection.IN, t_home)

    # Lunch window — only for morning arrivals, and only if they'll still be
    # in the building well past the return (otherwise the lunch badge-out
    # would land after their departure badge-out, breaking the narrative).
    lunch_out = rng.uniform(720, 780)
    lunch_back = lunch_out + rng.uniform(30, 60)
    lunch = arrival < 660 and departure > lunch_back + 60 and rng.random() < persona.lunch_prob

    # First login shortly after reaching the home zone; extras spread across
    # the day, skipping the lunch absence (nobody types while out to lunch).
    t_first = t_home + timedelta(minutes=rng.uniform(MIN_BADGE_TO_LOGIN_MIN, 10))
    writer.login(t_first, _workstation(emp), emp.home_zone)
    for _ in range(rng.randint(1, 3) - 1):
        minutes = rng.uniform(arrival + 40, departure - 20)
        if lunch and lunch_out <= minutes <= lunch_back:
            continue
        t_extra = _at(day, minutes)
        if t_extra > t_first:
            writer.login(t_extra, _workstation(emp), emp.home_zone)

    if lunch:
        writer.badge_event("LOBBY", BadgeDirection.OUT, _at(day, lunch_out))
        t_back = _at(day, lunch_back)
        writer.badge_event("LOBBY", BadgeDirection.IN, t_back)
        writer.badge_event(
            emp.home_zone, BadgeDirection.IN, t_back + timedelta(seconds=rng.randint(45, 180))
        )

    # Afternoon wander into a permitted visit zone; SRV-ROOM visits often
    # include a sensitive-host login (benign daytime noise for GB-004).
    visit_low = max(arrival + 60, lunch_back + 30 if lunch else 0)
    visit_high = departure - 90
    if persona.visit_zones and visit_high > visit_low and rng.random() < ZONE_VISIT_PROB:
        zone = rng.choice(persona.visit_zones)
        t_visit = _at(day, rng.uniform(visit_low, visit_high))
        writer.badge_event(zone, BadgeDirection.IN, t_visit)
        if zone == "SRV-ROOM" and rng.random() < SRV_LOGIN_PROB:
            t_srv = t_visit + timedelta(minutes=rng.uniform(MIN_BADGE_TO_LOGIN_MIN, 10))
            host = f"SRV-{_emp_num(emp) % 5 + 1:02d}"
            writer.login(t_srv, host, "SRV-ROOM", sensitive=True)
        writer.badge_event(
            emp.home_zone,
            BadgeDirection.IN,
            t_visit + timedelta(minutes=rng.uniform(30, 60)),
        )

    if rng.random() >= MISSING_BADGE_OUT_PROB:
        writer.badge_event("LOBBY", BadgeDirection.OUT, _at(day, departure))


def _workstation(employee: Employee) -> str:
    """Each employee owns one workstation in their home zone."""
    return f"WS-{employee.home_zone}-{_emp_num(employee):03d}"


def finalize_events(badge: list[BadgeEvent], auth: list[AuthEvent]) -> None:
    """Sort both streams by timestamp and assign sequential event ids.

    Ids are assigned only after the world is fully assembled (benign +
    injections) so they are gapless and stable — ground-truth labels
    reference these exact ids, and evidence chains depend on them.
    """
    badge.sort(key=lambda e: (e.ts, e.employee_id, e.door_id, e.direction))
    for i, event in enumerate(badge):
        event.event_id = f"b-{i + 1:06d}"
    auth.sort(key=lambda e: (e.ts, e.account, e.host))
    for i, event in enumerate(auth):
        event.event_id = f"a-{i + 1:06d}"
