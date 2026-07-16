"""GB-001 Ghost Login: an on-site login whose account owner never badged in."""

from ghostbadge.models import Alert, LoginType, Severity
from ghostbadge.rules.base import Rule, register_rule
from ghostbadge.rules.windows import DayWindow


@register_rule
class GhostLogin(Rule):
    """GB-001: Interactive login on an on-site host with no badge event that day.

    Attacker story: stolen or shared credentials used at a workstation while
    the real owner is absent (remote, on leave, or simply elsewhere). The
    auth log looks perfectly normal; only the badge system knows no body
    entered the building. Maps to T1078 (Valid Accounts).

    FP story: badge reader outage or an entrance with a broken reader makes
    honest on-site workers look ghostly. Mitigation: if more than
    `outage_threshold` of the accounts logging in interactively today have
    no badge trail at all, assume a systemic badge outage and suppress the
    day. (Deliberately measured against *interactive-login accounts*, not
    the whole workforce — on any normal weekday ~15% of staff is remote
    with no swipes, which would trip a workforce-wide check every day.)

    Evasion: the attacker also steals or clones the victim's badge and
    swipes in — then GB-003 (zone mismatch) or GB-006/GB-007 become the
    detection surface. A *denied* badge read still counts as physical
    presence here: it proves someone stood at a door with the card, which
    is a different (lesser) problem than credentials moving without a body.
    """

    id = "GB-001"
    name = "Ghost Login"
    severity = Severity.HIGH
    mitre_technique = "T1078"
    default_params = {"outage_threshold": 0.5, "confidence": 0.9}

    def evaluate(self, window: DayWindow) -> list[Alert]:
        ghosts: list[tuple[str, list]] = []
        n_onsite_loggers = 0
        for account, events in window.auth_by_account.items():
            if account not in window.employees:
                continue  # data-quality issue, not an alert (see windows.py)
            logins = [e for e in events if e.login_type is LoginType.INTERACTIVE]
            if not logins:
                continue
            n_onsite_loggers += 1
            if not window.badge_by_employee.get(account):
                ghosts.append((account, logins))

        if not ghosts:
            return []
        if len(ghosts) / n_onsite_loggers > self.params["outage_threshold"]:
            return []  # systemic badge outage, per FP story above

        alerts = []
        for account, logins in ghosts:
            first = logins[0]
            alerts.append(
                self.make_alert(
                    window=window,
                    employee_id=account,
                    evidence=[e.event_id for e in logins],
                    explanation=(
                        f"{account} logged into {first.host} at {first.ts:%H:%M} UTC "
                        f"but has no badge entry on {window.day.isoformat()}"
                    ),
                    confidence=self.params["confidence"],
                )
            )
        return alerts
