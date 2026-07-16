"""Byte-stable JSONL output for event and label streams.

Determinism tests hash these files, so everything that could vary is pinned:
pydantic field order fixes key order, timestamps serialize as `...Z` at
second precision, and lines always end in a bare LF.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel


def write_jsonl(records: Iterable[BaseModel], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        for record in records:
            f.write(json.dumps(record.model_dump(mode="json")) + "\n")
