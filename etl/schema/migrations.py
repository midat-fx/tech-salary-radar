"""Read a partition that was written by an older version of this code.

:mod:`etl.schema.version` states the compatibility rule and
:func:`etl.schema.validate.fill_missing` performs the fill. This is the piece
that connects them to an actual file — and it is the piece that was missing, so
the rule was written down and then not applied: the aggregator read every day
with one query and relied on DuckDB's NULL-fill, which is the accident ADR 0008
exists to replace with a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from etl.schema.fields import Table
from etl.schema.validate import fill_missing
from etl.schema.version import SCHEMA_VERSION, SchemaVersion, compatibility, describe

__all__ = ["PartitionRead", "read_partition_versioned", "detect_version", "MARKER_COLUMN"]

#: The column a partition stamps its schema version into. Absent on every
#: partition written before versioning existed, which is what makes an unmarked
#: partition detectable rather than merely old.
MARKER_COLUMN = "schema_version"


@dataclass(frozen=True)
class PartitionRead:
    """Rows from one day, plus what had to be done to make them readable."""

    rows: list[dict]
    written_with: SchemaVersion | None
    filled: tuple[str, ...] = ()
    note: str = ""

    @property
    def needed_fill(self) -> bool:
        return bool(self.filled)

    def describe(self) -> str:
        if not self.filled:
            return self.note
        return f"{self.note}; filled {', '.join(self.filled)}"


def detect_version(rows: list[dict]) -> SchemaVersion | None:
    """The version a partition was written with, from its marker column.

    Takes the *lowest* version present rather than the first row's. A partition
    that somehow mixes generations — a same-day append across a deploy — has to
    be read as the oldest thing in it, or a column added by the newer half goes
    unfilled for the older half.
    """
    stamped = [
        SchemaVersion.parse(row.get(MARKER_COLUMN))
        for row in rows
        if row.get(MARKER_COLUMN) is not None
    ]
    present = [version for version in stamped if version is not None]
    return min(present) if present else None


def read_partition_versioned(
    table: Table, path: str | Path, reader: SchemaVersion = SCHEMA_VERSION
) -> PartitionRead:
    """Read one partition file, filling what the version rule says to fill."""
    import pyarrow.parquet as pq

    target = Path(path)
    if not target.exists():
        return PartitionRead([], reader, note="no such partition")

    rows = pq.read_table(target).to_pylist()
    written = detect_version(rows)
    for row in rows:
        row.pop(MARKER_COLUMN, None)

    filled_rows, filled = fill_missing(table, rows, written)
    return PartitionRead(
        rows=filled_rows,
        written_with=written,
        filled=tuple(filled),
        note=describe(written, reader),
    )


def compatibility_of(path: str | Path, reader: SchemaVersion = SCHEMA_VERSION) -> str:
    """How a partition would be treated, without reading all of it."""
    import pyarrow.parquet as pq

    target = Path(path)
    if not target.exists():
        return "absent"
    head = pq.read_table(target).slice(0, 1).to_pylist()
    return compatibility(detect_version(head), reader)
