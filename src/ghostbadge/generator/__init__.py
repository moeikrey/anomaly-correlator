"""Synthetic data generator.

Produces the fake world GhostBadge detects against: an HR roster, badge-swipe
events, and network-auth events, all driven by a single master seed so any
dataset is exactly reproducible. Nothing here touches real data — names, IPs,
and geos come from hardcoded synthetic tables.
"""

from ghostbadge.generator.roster import generate_roster, write_roster_csv

__all__ = ["generate_roster", "write_roster_csv"]
