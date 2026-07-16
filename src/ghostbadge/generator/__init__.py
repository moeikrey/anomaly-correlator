"""Synthetic data generator.

Produces the fake world GhostBadge detects against: an HR roster, badge-swipe
events, network-auth events, and ground-truth labels for injected attack
scenarios — all driven by a single master seed so any dataset is exactly
reproducible. Nothing here touches real data — names, IPs, and geos come
from hardcoded synthetic tables.
"""

from ghostbadge.generator.events import finalize_events, generate_benign_events
from ghostbadge.generator.inject import (
    SCENARIOS,
    World,
    inject_scenarios,
    resolve_labels,
)
from ghostbadge.generator.roster import generate_roster, write_roster_csv
from ghostbadge.generator.write import write_jsonl

__all__ = [
    "SCENARIOS",
    "World",
    "finalize_events",
    "generate_benign_events",
    "generate_roster",
    "inject_scenarios",
    "resolve_labels",
    "write_jsonl",
    "write_roster_csv",
]
