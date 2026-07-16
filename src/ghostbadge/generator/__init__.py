"""Synthetic data generator.

Produces the fake world GhostBadge detects against: an HR roster, badge-swipe
events, and network-auth events, all driven by a single master seed so any
dataset is exactly reproducible. Nothing here touches real data — names, IPs,
and geos come from hardcoded synthetic tables.
"""

from ghostbadge.generator.events import finalize_events, generate_benign_events
from ghostbadge.generator.roster import generate_roster, write_roster_csv
from ghostbadge.generator.write import write_events_jsonl

__all__ = [
    "finalize_events",
    "generate_benign_events",
    "generate_roster",
    "write_events_jsonl",
    "write_roster_csv",
]
