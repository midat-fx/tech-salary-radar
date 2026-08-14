"""Write one day's rows as a parquet partition, canonically.

The partition is the unit of the history: one directory per table per day,
overwritten whole. Three properties make the commit that follows meaningful.

**Validated.** Every row is checked against its table before it is written, so a
malformed posting is dropped and counted rather than becoming a column of nulls
somebody discovers a month later. A duplicate key still raises: that means the
pipeline built the day wrong, not that a board sent something odd.

**Sorted.** Rows go out in key order, so re-running a day over unchanged data
produces an identical file and the git diff is empty. Without it every run
commits a new binary and the daily commit stops being evidence of anything.

**Whole.** A day is replaced, never appended to — except for the skills table,
where a second run of the same day legitimately labels what the budget did not
reach the first time.
"""

from __future__ import annotations

from pathlib import Path

from etl.schema import table_for, validate_partition

__all__ = ["partition_path", "write_partition", "read_partition", "WriteResult"]


def partition_path(data_dir: str | Path, table: str, day: str) -> Path:
    return Path(data_dir) / table / f"dt={day}" / "part.parquet"


class WriteResult(tuple):
    """``(path, rejected)``. A tuple so the common ``path = write(...)`` still reads."""

    __slots__ = ()

    def __new__(cls, path, rejected):
        return super().__new__(cls, (path, rejected))

    @property
    def path(self):
        return self[0]

    @property
    def rejected(self):
        return self[1]


def read_partition(data_dir: str | Path, table: str, day: str) -> list[dict]:
    """The rows already stored for a day, or an empty list."""
    import pyarrow.parquet as pq

    path = partition_path(data_dir, table, day)
    return pq.read_table(path).to_pylist() if path.exists() else []


def write_partition(rows, data_dir, table, dt, append=False, log=None):
    """Write a day. Returns the path, or ``None`` when there was nothing to write.

    An empty day removes any stale file rather than writing a columnless
    parquet, which is unreadable — and leaving yesterday's file in place under
    today's partition name would be worse than either.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    spec = table_for(table)
    out = partition_path(data_dir, table, dt)
    if append and out.exists():
        rows = read_partition(data_dir, table, dt) + list(rows)

    rows, rejected = validate_partition(spec, rows)
    if rejected and log:
        log(f"{table} {dt}: dropped {len(rejected)} unstorable rows, first: {rejected[0].reason}")
    if not rows:
        if out.exists():
            out.unlink()
        return None

    out.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows).sort_values(list(spec.key)).reset_index(drop=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), out, compression="zstd")
    return out
