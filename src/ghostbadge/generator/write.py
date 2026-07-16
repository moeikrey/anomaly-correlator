"""Byte-stable JSONL output for event streams.

Determinism tests hash these files, so everything that could vary is pinned:
pydantic field order fixes key order, timestamps serialize as `...Z` at
second precision, and lines always end in a bare LF.
"""

import json
from pathlib import Path

from ghostbadge.models import AuthEvent, BadgeEvent


def write_events_jsonl(events: list[BadgeEvent] | list[AuthEvent], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        for event in events:
            f.write(json.dumps(event.model_dump(mode="json")) + "\n")
