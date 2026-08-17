"""Which fields of a normalised record each stored table takes.

Two projections of one record. They overlap heavily and differ in a way that is
easy to get wrong by hand: the snapshot is the *daily* view and carries only
what a filter or a median needs, while the jobs table is the *inflow* view and
carries everything a reader might want about a posting seen once.

Derived from the schema rather than repeated, so a column added to the table
specification cannot be silently absent from the rows written into it.
"""

from __future__ import annotations

from etl.schema import JOBS, SNAPSHOTS

__all__ = ["SNAPSHOT_COLUMNS", "JOB_COLUMNS", "project"]

SNAPSHOT_COLUMNS = SNAPSHOTS.names
JOB_COLUMNS = JOBS.names


def project(record: dict, columns) -> dict:
    """Take exactly ``columns`` from a record, with ``None`` for anything absent.

    ``None`` rather than raising: a record is built by several layers and a
    field one of them did not produce is a nullable column, not a crash. The
    writer's validation is what refuses a column that may not be null.
    """
    return {name: record.get(name) for name in columns}
