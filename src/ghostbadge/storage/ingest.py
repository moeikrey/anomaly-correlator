"""Ingestion: validate at the border, reject-and-log, load into SQLite.

A correlator that crashes on one malformed log line is a correlator an
attacker can disable with one malformed log line. Every row is validated
through the pydantic models; rows that fail are rejected loudly (file, line
number, first reason) and counted, but never block the rest of the load.
Duplicate or missing event ids are rejected too — they would corrupt
evidence chains, which must point at exactly one stored event.
"""

import csv
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ghostbadge.models import AuthEvent, BadgeEvent, Employee, Label
from ghostbadge.storage.schema import (
    AuthEventRow,
    BadgeEventRow,
    EmployeeRow,
    LabelRow,
    get_engine,
    init_db,
)

logger = logging.getLogger("ghostbadge.ingest")


class StreamReport(BaseModel):
    loaded: int = 0
    rejected: int = 0


class IngestReport(BaseModel):
    employees: StreamReport = Field(default_factory=StreamReport)
    badge_events: StreamReport = Field(default_factory=StreamReport)
    auth_events: StreamReport = Field(default_factory=StreamReport)
    labels: StreamReport = Field(default_factory=StreamReport)

    @property
    def total_rejected(self) -> int:
        return sum(
            s.rejected for s in (self.employees, self.badge_events, self.auth_events, self.labels)
        )


def _brief(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        err = exc.errors()[0]
        loc = ".".join(str(part) for part in err["loc"]) or "row"
        return f"{loc}: {err['msg']}"
    return str(exc).splitlines()[0]


def _reject(report: StreamReport, path: Path, lineno: int, reason: str) -> None:
    logger.warning("%s line %d rejected: %s", path.name, lineno, reason)
    report.rejected += 1


M = TypeVar("M", bound=BaseModel)


def _load_jsonl(
    path: Path,
    model_cls: type[M],
    report: StreamReport,
    seen_ids: set[str] | None = None,
) -> list[M]:
    """Parse a JSONL file line by line; bad lines are logged, not fatal."""
    models: list[M] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                model = model_cls.model_validate_json(line)
            except ValidationError as exc:
                _reject(report, path, lineno, _brief(exc))
                continue
            if seen_ids is not None:
                event_id = model.event_id  # type: ignore[attr-defined]
                if not event_id:
                    _reject(report, path, lineno, "empty event_id")
                    continue
                if event_id in seen_ids:
                    _reject(report, path, lineno, f"duplicate event_id {event_id}")
                    continue
                seen_ids.add(event_id)
            models.append(model)
            report.loaded += 1
    return models


def _load_roster(path: Path, report: StreamReport) -> list[Employee]:
    employees: list[Employee] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        # DictReader consumes the header, so data starts at line 2.
        for lineno, row in enumerate(csv.DictReader(f), 2):
            try:
                employee = Employee(
                    employee_id=row.get("employee_id") or "",
                    name=row.get("name") or "",
                    department=row.get("department") or "",
                    home_zone=row.get("home_zone") or "",
                    permitted_zones=[z for z in (row.get("permitted_zones") or "").split(";") if z],
                    status=row.get("status") or "",
                    term_date=row.get("term_date") or None,
                )
            except ValidationError as exc:
                _reject(report, path, lineno, _brief(exc))
                continue
            if not employee.employee_id:
                _reject(report, path, lineno, "empty employee_id")
                continue
            if employee.employee_id in seen:
                _reject(report, path, lineno, f"duplicate employee_id {employee.employee_id}")
                continue
            seen.add(employee.employee_id)
            employees.append(employee)
            report.loaded += 1
    return employees


def ingest_dir(data_dir: Path, db_path: Path | None = None) -> IngestReport:
    """Load a generated dataset directory into SQLite (full reload).

    Requires hr_roster.csv, badge_events.jsonl, and auth_events.jsonl;
    labels.jsonl is optional because real deployments have no ground truth —
    only synthetic worlds do.
    """
    roster_path = data_dir / "hr_roster.csv"
    badge_path = data_dir / "badge_events.jsonl"
    auth_path = data_dir / "auth_events.jsonl"
    labels_path = data_dir / "labels.jsonl"
    for required in (roster_path, badge_path, auth_path):
        if not required.exists():
            raise FileNotFoundError(f"missing required input: {required}")

    report = IngestReport()
    employees = _load_roster(roster_path, report.employees)
    badge = _load_jsonl(badge_path, BadgeEvent, report.badge_events, seen_ids=set())
    auth = _load_jsonl(auth_path, AuthEvent, report.auth_events, seen_ids=set())
    labels: list[Label] = []
    if labels_path.exists():
        labels = _load_jsonl(labels_path, Label, report.labels)

    engine = get_engine(db_path or data_dir / "ghostbadge.db")
    init_db(engine)
    with Session(engine) as session:
        session.add_all(EmployeeRow.from_model(e) for e in employees)
        session.add_all(BadgeEventRow.from_model(e) for e in badge)
        session.add_all(AuthEventRow.from_model(e) for e in auth)
        session.add_all(LabelRow.from_model(label) for label in labels)
        session.commit()
    return report
