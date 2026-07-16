"""Core data models shared across the generator, ingestion, and rule engine.

These models are the contract between modules: anything that crosses a module
boundary is a pydantic model, validated at the border. Security rationale:
correlation rules reason about *identity* (who badged, who logged in) and
*authorization state* (active vs. terminated, which zones are permitted).
Getting those facts wrong at the model layer silently poisons every detection
downstream, so they are typed and validated here, once.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, field_serializer, field_validator, model_validator


class EmployeeStatus(StrEnum):
    """HR lifecycle state.

    A `terminated` employee is the highest-signal actor in the dataset: any
    badge or auth activity after their term date is by definition unauthorized
    (GB-005). The enum is deliberately binary — leave/contractor nuances would
    dilute that signal without adding detection value.
    """

    ACTIVE = "active"
    TERMINATED = "terminated"


class Employee(BaseModel):
    """One row of the HR roster.

    The roster is the authorization ground truth that physical and cyber logs
    are correlated against: `permitted_zones` defines where a badge *should*
    appear, and `status`/`term_date` define *when* any activity is legitimate
    at all. All names and identifiers are synthetic.
    """

    employee_id: str
    name: str
    department: str
    home_zone: str
    permitted_zones: list[str]
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    term_date: date | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> "Employee":
        if self.home_zone not in self.permitted_zones:
            raise ValueError(f"home_zone {self.home_zone!r} missing from permitted_zones")
        if (self.status is EmployeeStatus.TERMINATED) != (self.term_date is not None):
            raise ValueError("term_date must be set iff status is terminated")
        return self


class Label(BaseModel):
    """Ground-truth row for one injected attack instance.

    The generator's contract with the scoring pipeline: every malicious
    event injected into the synthetic world is recorded here, and
    `ghostbadge score` measures each rule's precision/recall against these
    rows. An injection without a label would silently deflate measured
    precision — never inject without labeling.
    """

    scenario: str
    rule_id_expected: str
    employee_id: str
    event_ids: list[str]
    day: date


class BadgeDirection(StrEnum):
    IN = "in"
    OUT = "out"


class BadgeResult(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"


class LoginType(StrEnum):
    INTERACTIVE = "interactive"
    VPN = "vpn"


class GeoPoint(BaseModel):
    """Coarse city-level location attached to VPN logins.

    City-level only, from a hardcoded table — precise enough for
    impossible-presence distance math (GB-002), never precise enough to
    locate a person. Field order matters: it fixes JSONL key order.
    """

    lat: float
    lon: float
    city: str


class _TimestampedEvent(BaseModel):
    """Shared base: every event has an id and a UTC timestamp.

    Correlation is fundamentally *temporal* — rules ask "did the badge-in
    precede the login?" — so a naive or non-UTC timestamp anywhere breaks
    every detection at once. Awareness is enforced here at the model border.
    """

    event_id: str = ""  # assigned at world finalization, in timestamp order
    ts: datetime

    @field_validator("ts")
    @classmethod
    def _require_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware (UTC)")
        return v

    @field_serializer("ts")
    def _serialize_ts(self, v: datetime) -> str:
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")


class BadgeEvent(_TimestampedEvent):
    """One physical badge read at a zone door.

    The physical half of every correlation: rules treat a granted badge-in
    as proof of bodily presence in a zone. Denied reads are kept (not
    dropped) because an attacker probing doors looks exactly like a burst
    of denies.
    """

    employee_id: str
    door_id: str
    zone: str
    direction: BadgeDirection
    result: BadgeResult


class AuthEvent(_TimestampedEvent):
    """One network authentication (interactive workstation login or VPN).

    The cyber half of every correlation. `host_zone` ties a workstation to
    physical space (interactive only); `geo` ties a VPN session to the
    world map (vpn only). That split is enforced here because a VPN event
    with a host zone — or a local login with a geo — would let a single
    malformed record satisfy both sides of a correlation at once.
    """

    account: str
    host: str
    host_zone: str | None
    login_type: LoginType
    src_ip: str
    geo: GeoPoint | None = None
    sensitive: bool = False
    result: str = "success"

    @model_validator(mode="after")
    def _check_type_consistency(self) -> "AuthEvent":
        if self.login_type is LoginType.VPN:
            if self.host_zone is not None:
                raise ValueError("vpn logins have no physical host_zone")
            if self.geo is None:
                raise ValueError("vpn logins must carry a geo")
        else:
            if self.host_zone is None:
                raise ValueError("interactive logins must carry a host_zone")
            if self.geo is not None:
                raise ValueError("interactive logins must not carry a geo")
        return self
