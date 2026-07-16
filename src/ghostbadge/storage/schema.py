"""SQLite schema and model<->row conversion.

Events keep their source event ids as primary keys because evidence chains
are sacred: an alert must be able to cite the exact stored rows that
triggered it, and those ids must survive the trip through the database
unchanged. Timestamps go through `UTCDateTime`, which refuses naive values
on write and re-attaches UTC on read — SQLite itself has no timezone
concept, so without this guard a round-trip would silently strip awareness
and violate the all-timestamps-UTC convention.
"""

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from ghostbadge.models import AuthEvent, BadgeEvent, Employee, Label


class UTCDateTime(TypeDecorator):
    """Stores aware UTC datetimes as naive-UTC; restores awareness on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("refusing to store a naive datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class EmployeeRow(Base):
    __tablename__ = "employees"

    employee_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    department: Mapped[str]
    home_zone: Mapped[str]
    permitted_zones: Mapped[list] = mapped_column(JSON)
    status: Mapped[str]
    term_date: Mapped[date | None]

    @classmethod
    def from_model(cls, e: Employee) -> "EmployeeRow":
        return cls(
            employee_id=e.employee_id,
            name=e.name,
            department=e.department,
            home_zone=e.home_zone,
            permitted_zones=list(e.permitted_zones),
            status=e.status.value,
            term_date=e.term_date,
        )

    def to_model(self) -> Employee:
        return Employee(
            employee_id=self.employee_id,
            name=self.name,
            department=self.department,
            home_zone=self.home_zone,
            permitted_zones=list(self.permitted_zones),
            status=self.status,
            term_date=self.term_date,
        )


class BadgeEventRow(Base):
    __tablename__ = "badge_events"

    event_id: Mapped[str] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    employee_id: Mapped[str] = mapped_column(index=True)
    door_id: Mapped[str]
    zone: Mapped[str]
    direction: Mapped[str]
    result: Mapped[str]

    @classmethod
    def from_model(cls, e: BadgeEvent) -> "BadgeEventRow":
        return cls(
            event_id=e.event_id,
            ts=e.ts,
            employee_id=e.employee_id,
            door_id=e.door_id,
            zone=e.zone,
            direction=e.direction.value,
            result=e.result.value,
        )

    def to_model(self) -> BadgeEvent:
        return BadgeEvent(
            event_id=self.event_id,
            ts=self.ts,
            employee_id=self.employee_id,
            door_id=self.door_id,
            zone=self.zone,
            direction=self.direction,
            result=self.result,
        )


class AuthEventRow(Base):
    __tablename__ = "auth_events"

    event_id: Mapped[str] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    account: Mapped[str] = mapped_column(index=True)
    host: Mapped[str]
    host_zone: Mapped[str | None]
    login_type: Mapped[str]
    src_ip: Mapped[str]
    geo: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sensitive: Mapped[bool]
    result: Mapped[str]

    @classmethod
    def from_model(cls, e: AuthEvent) -> "AuthEventRow":
        return cls(
            event_id=e.event_id,
            ts=e.ts,
            account=e.account,
            host=e.host,
            host_zone=e.host_zone,
            login_type=e.login_type.value,
            src_ip=e.src_ip,
            geo=e.geo.model_dump() if e.geo is not None else None,
            sensitive=e.sensitive,
            result=e.result,
        )

    def to_model(self) -> AuthEvent:
        return AuthEvent(
            event_id=self.event_id,
            ts=self.ts,
            account=self.account,
            host=self.host,
            host_zone=self.host_zone,
            login_type=self.login_type,
            src_ip=self.src_ip,
            geo=self.geo,
            sensitive=self.sensitive,
            result=self.result,
        )


class LabelRow(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario: Mapped[str]
    rule_id_expected: Mapped[str] = mapped_column(index=True)
    employee_id: Mapped[str]
    event_ids: Mapped[list] = mapped_column(JSON)
    day: Mapped[date]

    @classmethod
    def from_model(cls, label: Label) -> "LabelRow":
        return cls(
            scenario=label.scenario,
            rule_id_expected=label.rule_id_expected,
            employee_id=label.employee_id,
            event_ids=list(label.event_ids),
            day=label.day,
        )

    def to_model(self) -> Label:
        return Label(
            scenario=self.scenario,
            rule_id_expected=self.rule_id_expected,
            employee_id=self.employee_id,
            event_ids=list(self.event_ids),
            day=self.day,
        )


def get_engine(db_path: Path) -> Engine:
    return create_engine(f"sqlite:///{db_path.as_posix()}")


def init_db(engine: Engine) -> None:
    """Reset the database: ingestion is an idempotent full reload."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
