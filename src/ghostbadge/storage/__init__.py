"""Ingestion and SQLite storage.

The border between untrusted input files and the correlation engine:
everything in the database has passed pydantic validation, carries a unique
event id, and has a timezone-aware UTC timestamp.
"""

from ghostbadge.storage.ingest import IngestReport, StreamReport, ingest_dir
from ghostbadge.storage.schema import (
    AuthEventRow,
    BadgeEventRow,
    EmployeeRow,
    LabelRow,
    get_engine,
    init_db,
)

__all__ = [
    "AuthEventRow",
    "BadgeEventRow",
    "EmployeeRow",
    "IngestReport",
    "LabelRow",
    "StreamReport",
    "get_engine",
    "ingest_dir",
    "init_db",
]
