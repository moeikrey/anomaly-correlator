"""Rule base class and registry.

A rule is a falsifiable claim about attacker behavior expressed as code.
Every concrete rule's docstring must answer three questions: what attacker
behavior does this catch, what benign behavior could look identical (the
false-positive story), and what could an attacker do to evade it. Thresholds
live in `default_params` and are overridable per instance, so tuning false
positives never requires a code edit.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ghostbadge.models import Alert, Severity
from ghostbadge.rules.windows import DayWindow


class Rule(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    severity: ClassVar[Severity]
    mitre_technique: ClassVar[str]
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params: dict[str, Any] = {**self.default_params, **(params or {})}

    @abstractmethod
    def evaluate(self, window: DayWindow) -> list[Alert]:
        """Pure: reads the window, returns alerts. No I/O, no global state."""

    def make_alert(
        self,
        *,
        window: DayWindow,
        employee_id: str,
        evidence: list[str],
        explanation: str,
        confidence: float,
    ) -> Alert:
        return Alert(
            rule_id=self.id,
            rule_name=self.name,
            severity=self.severity,
            mitre_technique=self.mitre_technique,
            confidence=confidence,
            employee_id=employee_id,
            day=window.day,
            evidence_event_ids=evidence,
            explanation=explanation,
        )


RULE_REGISTRY: dict[str, type[Rule]] = {}


def register_rule(cls: type[Rule]) -> type[Rule]:
    if cls.id in RULE_REGISTRY:
        raise ValueError(f"duplicate rule id {cls.id}")
    RULE_REGISTRY[cls.id] = cls
    return cls


def all_rules(params: dict[str, dict[str, Any]] | None = None) -> list[Rule]:
    """Instantiate every registered rule, ordered by id, with optional overrides."""
    overrides = params or {}
    return [cls(overrides.get(rule_id)) for rule_id, cls in sorted(RULE_REGISTRY.items())]
