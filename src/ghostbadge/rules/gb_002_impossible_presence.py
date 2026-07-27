"""GB-002 Impossible Presence: physically at HQ, yet a VPN login from far away."""

from ghostbadge.geo import km_from_hq
from ghostbadge.models import Alert, BadgeResult, LoginType, Severity
from ghostbadge.rules.base import Rule, register_rule
from ghostbadge.rules.windows import DayWindow


@register_rule
class ImpossiblePresence(Rule):
    """GB-002: a badge read at HQ and a VPN login from a geo too far to travel.

    Attacker story: the account owner is physically in the building (their
    badge proves it), while their credentials authenticate over VPN from
    another continent. One of the two sessions is not them — stolen
    credentials used remotely, or a session hijacked while the real user is
    at their desk. Neither log alone is suspicious; the contradiction only
    appears when physical and cyber are put on the same clock. Maps to
    T1078 (Valid Accounts).

    FP story: a genuinely mobile employee — badges out at lunch, tethers,
    and VPNs from a nearby city. Mitigation: the bar is *physics*, not mere
    distance. We fire only when distance / available-time exceeds
    `max_kph` (900 km/h, faster than any commercial flight), and we credit
    the traveler the full clock-skew budget (`skew_seconds`) as extra travel
    time so jitter between the badge and auth clocks can never manufacture
    an alert. Benign VPNs from the commute cities (<70 km) never approach
    the threshold. A *denied* badge read is not counted as HQ presence: it
    proves a card was at the door, not that this body was admitted, so it is
    too ambiguous to anchor a physics claim on.

    Evasion: route the remote login through a VPN exit near HQ so the geo
    looks local — then the impossible-speed signal vanishes and the burden
    shifts to GB-007 (same credentials, two zones, no badge movement) or to
    behavioral/ML layers. Widening the elapsed window (waiting hours between
    the badge and the remote login) also defeats it, by design: past a real
    travel time it is no longer impossible presence.
    """

    id = "GB-002"
    name = "Impossible Presence"
    severity = Severity.HIGH
    mitre_technique = "T1078"
    default_params = {"max_kph": 900.0, "skew_seconds": 180, "confidence": 0.95}

    def evaluate(self, window: DayWindow) -> list[Alert]:
        alerts: list[Alert] = []
        for account, events in window.auth_by_account.items():
            if account not in window.employees:
                continue  # data-quality issue, not an alert (see windows.py)

            # Granted badge reads are the only accepted proof the body was at
            # HQ; each carries a timestamp we can race the VPN login against.
            presence = [
                b
                for b in window.badge_by_employee.get(account, [])
                if b.result is BadgeResult.GRANTED
            ]
            if not presence:
                continue
            vpn_logins = [e for e in events if e.login_type is LoginType.VPN and e.geo is not None]
            if not vpn_logins:
                continue

            worst: tuple[float, object, object] | None = None  # (kph, vpn, badge)
            impossible_ids: list[str] = []
            for vpn in vpn_logins:
                # Closest-in-time badge read is the tightest constraint: it
                # leaves the least time to cover the distance, so if even it
                # is not survivable, no read that day is.
                badge = min(presence, key=lambda b: abs((vpn.ts - b.ts).total_seconds()))
                gap_s = abs((vpn.ts - badge.ts).total_seconds()) + self.params["skew_seconds"]
                kph = km_from_hq(vpn.geo.lat, vpn.geo.lon) / (gap_s / 3600)
                if kph > self.params["max_kph"]:
                    impossible_ids += [vpn.event_id, badge.event_id]
                    if worst is None or kph > worst[0]:
                        worst = (kph, vpn, badge)

            if worst is None:
                continue
            _, vpn, badge = worst
            alerts.append(
                self.make_alert(
                    window=window,
                    employee_id=account,
                    # Deduplicate while preserving order (a badge read can
                    # anchor more than one impossible VPN in the same day).
                    evidence=list(dict.fromkeys(impossible_ids)),
                    explanation=(
                        f"{account} badged in at HQ at {badge.ts:%H:%M} UTC but authenticated "
                        f"over VPN from {vpn.geo.city} at {vpn.ts:%H:%M} UTC on "
                        f"{window.day.isoformat()} — {km_from_hq(vpn.geo.lat, vpn.geo.lon):.0f} km "
                        f"apart, impossibly fast for the elapsed time"
                    ),
                    confidence=self.params["confidence"],
                )
            )
        return alerts
