"""Correlation rules: pure detections over per-day event windows.

Importing this package registers every rule module; `all_rules()` returns
ready-to-run instances ordered by id.
"""

from ghostbadge.rules import gb_001_ghost_login  # noqa: F401  (registers GB-001)
from ghostbadge.rules.base import RULE_REGISTRY, Rule, all_rules, register_rule
from ghostbadge.rules.windows import DayWindow, build_day_windows

__all__ = [
    "RULE_REGISTRY",
    "DayWindow",
    "Rule",
    "all_rules",
    "build_day_windows",
    "register_rule",
]
