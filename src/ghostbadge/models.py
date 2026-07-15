"""Core data models shared across the generator, ingestion, and rule engine.

These models are the contract between modules: anything that crosses a module
boundary is a pydantic model, validated at the border. Security rationale:
correlation rules reason about *identity* (who badged, who logged in) and
*authorization state* (active vs. terminated, which zones are permitted).
Getting those facts wrong at the model layer silently poisons every detection
downstream, so they are typed and validated here, once.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, model_validator


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
