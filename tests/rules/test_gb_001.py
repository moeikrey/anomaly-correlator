"""GB-001 Ghost Login: mandatory test trio (+ denied-badge look-alike)."""

from factories import badge, emp, login, ts, window

from ghostbadge.rules.gb_001_ghost_login import GhostLogin


def test_fires_on_login_without_badge_entry() -> None:
    """E001 logs in on-site with no badge trail; E002 is a normal office day."""
    w = window(
        employees=[emp("E001"), emp("E002")],
        badge_events=[badge("b-1", "E002", ts(8, 1))],
        auth_events=[
            login("a-1", "E001", ts(10, 30)),
            login("a-2", "E002", ts(8, 10)),
        ],
    )
    alerts = GhostLogin().evaluate(w)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule_id == "GB-001"
    assert alert.employee_id == "E001"
    assert alert.evidence_event_ids == ["a-1"]
    assert "no badge entry" in alert.explanation


def test_silent_when_owner_badged_in_elsewhere() -> None:
    """Nearest benign look-alike: badged in through a different zone's door."""
    w = window(
        employees=[emp("E001")],
        badge_events=[badge("b-1", "E001", ts(8, 0), zone="LOBBY")],
        auth_events=[login("a-1", "E001", ts(9, 0))],
    )
    assert GhostLogin().evaluate(w) == []


def test_silent_on_denied_badge_read() -> None:
    """A denied read still proves a body at a door — not a ghost."""
    w = window(
        employees=[emp("E001"), emp("E002")],
        badge_events=[
            badge("b-1", "E001", ts(8, 0), result="denied"),
            badge("b-2", "E002", ts(8, 1)),
        ],
        auth_events=[login("a-1", "E001", ts(9, 0)), login("a-2", "E002", ts(9, 5))],
    )
    assert GhostLogin().evaluate(w) == []


def test_edge_systemic_outage_is_suppressed() -> None:
    """Badge system down: every on-site logger looks ghostly -> suppress day."""
    employees = [emp(f"E00{i}") for i in (1, 2, 3)]
    w = window(
        employees=employees,
        badge_events=[],
        auth_events=[login(f"a-{i}", f"E00{i}", ts(9, i)) for i in (1, 2, 3)],
    )
    assert GhostLogin().evaluate(w) == []
    # ...but a lone ghost among badged colleagues is NOT an outage.
    assert GhostLogin(params={"outage_threshold": 1.0}).evaluate(w) != []
