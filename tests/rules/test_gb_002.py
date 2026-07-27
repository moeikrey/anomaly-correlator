"""GB-002 Impossible Presence: mandatory test trio (+ denied-badge look-alike)."""

from factories import badge, emp, login, ts, window

from ghostbadge.models import GeoPoint
from ghostbadge.rules.gb_002_impossible_presence import ImpossiblePresence

TOKYO = GeoPoint(lat=35.6762, lon=139.6503, city="Tokyo")  # ~8280 km from HQ
SAN_JOSE = GeoPoint(lat=37.3382, lon=-121.8863, city="San Jose")  # ~67 km (commute)
LOS_ANGELES = GeoPoint(lat=34.0522, lon=-118.2437, city="Los Angeles")  # ~559 km


def _vpn(event_id: str, account: str, when, geo: GeoPoint):
    return login(event_id, account, when, zone=None, geo=geo)


def test_fires_on_hq_badge_and_distant_vpn() -> None:
    """E001 badges into HQ, then VPNs from Tokyo 30 min later; E002 is benign."""
    w = window(
        employees=[emp("E001"), emp("E002")],
        badge_events=[
            badge("b-1", "E001", ts(9, 0), zone="LOBBY"),
            badge("b-2", "E002", ts(8, 30), zone="LOBBY"),
        ],
        auth_events=[
            _vpn("a-1", "E001", ts(9, 30), TOKYO),
            login("a-2", "E002", ts(8, 40)),  # ordinary on-site login
        ],
    )
    alerts = ImpossiblePresence().evaluate(w)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == "GB-002"
    assert alert.employee_id == "E001"
    assert set(alert.evidence_event_ids) == {"a-1", "b-1"}
    assert "Tokyo" in alert.explanation


def test_silent_on_nearby_vpn() -> None:
    """Nearest benign look-alike: badged in, then VPN from a commute city.

    ~67 km over 20 minutes is ~175 km/h — mobile, not teleporting.
    """
    w = window(
        employees=[emp("E001")],
        badge_events=[badge("b-1", "E001", ts(9, 0), zone="LOBBY")],
        auth_events=[_vpn("a-1", "E001", ts(9, 20), SAN_JOSE)],
    )
    assert ImpossiblePresence().evaluate(w) == []


def test_edge_uses_closest_badge_read() -> None:
    """Two badge reads bracket the VPN; only the near one makes it impossible.

    LA is ~559 km away: impossible 10 min after the 09:00 read (~2600 km/h),
    but trivially reachable versus the 17:00 read (~70 km/h). The rule must
    race the VPN against the *closest* read, or it would miss this.
    """
    w = window(
        employees=[emp("E001")],
        badge_events=[
            badge("b-morning", "E001", ts(9, 0), zone="LOBBY"),
            badge("b-evening", "E001", ts(17, 0), zone="LOBBY"),
        ],
        auth_events=[_vpn("a-1", "E001", ts(9, 10), LOS_ANGELES)],
    )
    alerts = ImpossiblePresence().evaluate(w)
    assert len(alerts) == 1
    assert "a-1" in alerts[0].evidence_event_ids
    assert "b-morning" in alerts[0].evidence_event_ids
    assert "b-evening" not in alerts[0].evidence_event_ids


def test_silent_when_only_badge_read_is_denied() -> None:
    """A denied read is not confirmed HQ presence, so no physics claim holds."""
    w = window(
        employees=[emp("E001")],
        badge_events=[badge("b-1", "E001", ts(9, 0), zone="LOBBY", result="denied")],
        auth_events=[_vpn("a-1", "E001", ts(9, 30), TOKYO)],
    )
    assert ImpossiblePresence().evaluate(w) == []
