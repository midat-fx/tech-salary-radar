"""Check a row against its table, and fill an older partition's missing columns.

Two directions, both needed, and easy to confuse:

* **Writing** — a row about to be stored must carry exactly the declared
  columns, with values of the declared types, and must not say something
  impossible. Anything else is caught here rather than becoming a published
  number nobody can explain.
* **Reading** — a partition written before a column existed must be readable,
  with the absent column filled by its declared default and the fill *reported*,
  not performed silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from etl.schema.errors import (
    InvariantViolated,
    MissingColumn,
    SchemaError,
    UnknownColumn,
    WrongType,
)
from etl.schema.fields import Table
from etl.schema.version import SchemaVersion, is_readable

__all__ = [
    "Rejected",
    "check_invariants",
    "coerce_row",
    "fill_missing",
    "validate_partition",
    "validate_row",
    "validate_rows",
]

#: bool before int on purpose: in Python ``True`` is an ``int``, and a boolean
#: landing in a numeric column is a real mistake worth catching.
_NUMERIC = (int, float)


def _acceptable(value: Any, kind: type) -> bool:
    if kind is bool:
        return isinstance(value, bool)
    if kind is float:
        return isinstance(value, _NUMERIC) and not isinstance(value, bool)
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def coerce_row(table: Table, row: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``row`` with numeric columns widened to float and nothing else changed.

    Parquet stores one type per column, and a column that is int in one day's
    partition and float in the next cannot be read back as a single view. The
    salary columns are the ones this happens to: an Ashby range of exactly
    ``180000`` arrives as an int while a converted EUR figure never does.
    """
    out = dict(row)
    for f in table.fields:
        value = out.get(f.name)
        if f.kind is float and isinstance(value, int) and not isinstance(value, bool):
            out[f.name] = float(value)
    return out


def validate_row(table: Table, row: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce, then check columns, types and invariants. Returns the storable row."""
    row = coerce_row(table, row)
    declared = set(table.names)
    for name in row:
        if name not in declared:
            raise UnknownColumn(table.name, name)
    for f in table.fields:
        if f.name not in row:
            raise MissingColumn(table.name, f.name)
        value = row[f.name]
        if value is None:
            if not f.nullable:
                raise MissingColumn(table.name, f.name)
            continue
        if not _acceptable(value, f.kind):
            raise WrongType(table.name, f.name, value)
    check_invariants(table, row)
    return row


def validate_rows(table: Table, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate every row, and check the properties that only hold across a partition."""
    out = [validate_row(table, row) for row in rows]
    seen: set[tuple[Any, ...]] = set()
    for row in out:
        identity = tuple(row[k] for k in table.key)
        if identity in seen:
            raise InvariantViolated(table.name, f"duplicate key {identity}")
        seen.add(identity)
    return out


def check_invariants(table: Table, row: Mapping[str, Any]) -> None:
    """Statements a well-typed row can still get wrong.

    Each of these has produced a wrong published number rather than a missing
    one, which is why they are refused at the writer instead of filtered at the
    reader.
    """
    lo, hi = row.get("salary_min_usd"), row.get("salary_max_usd")
    if lo is not None and hi is not None and lo > hi:
        raise InvariantViolated(table.name, f"salary_min_usd {lo} above salary_max_usd {hi}")

    if "has_salary" in row:
        mid = row.get("salary_mid_usd")
        if row["has_salary"] and mid is None:
            raise InvariantViolated(table.name, "has_salary is set but salary_mid_usd is null")
        if not row["has_salary"] and mid is not None:
            raise InvariantViolated(
                table.name, f"salary_mid_usd {mid} present while has_salary is false"
            )

    if "region" in row and row["region"] not in {"us", "eu", "other"}:
        raise InvariantViolated(table.name, f"region {row['region']!r} is outside the bucket set")

    uid = row.get("job_uid")
    if uid is not None and uid.count(":") < 2:
        raise InvariantViolated(table.name, f"job_uid {uid!r} is not source:company:job_id")


def fill_missing(
    table: Table, rows: Iterable[Mapping[str, Any]], written: SchemaVersion | None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read an older partition: add absent columns from their defaults.

    Returns the rows and the names that had to be filled, so a caller can put
    the list in the run report. A silent fill is the failure mode this whole
    module exists to prevent — it turns "this day could not have known" into
    "this day says no", and the two aggregate very differently.
    """
    if not is_readable(written):
        raise InvariantViolated(
            table.name, f"partition schema {written} is a different major; refusing to read"
        )
    materialised = [dict(r) for r in rows]
    present = set().union(*(set(r) for r in materialised)) if materialised else set()
    filled = [f.name for f in table.fields if f.name not in present]
    defaults = table.defaults()
    for row in materialised:
        for name in filled:
            row[name] = defaults[name]
    return materialised, sorted(filled)


@dataclass(frozen=True)
class Rejected:
    """A row that cannot be stored, and the reason, kept together for the report."""

    row: Mapping[str, Any]
    reason: str

    @property
    def uid(self) -> str:
        return str(self.row.get("job_uid", "?"))


def validate_partition(table: Table, rows: Iterable[Mapping[str, Any]]) -> tuple[list, list]:
    """Split a day into storable rows and rejects, then check the partition as a whole.

    Row-level violations drop the row: one malformed posting out of six thousand
    must not cost the day, and the count belongs in the run report where it can
    be watched. Partition-level violations — a duplicate key — still raise,
    because they mean the pipeline built the day wrong rather than a board
    sending something odd.
    """
    kept: list[dict[str, Any]] = []
    rejected: list[Rejected] = []
    for row in rows:
        try:
            kept.append(validate_row(table, row))
        except SchemaError as exc:
            rejected.append(Rejected(dict(row), str(exc)))
    seen: set[tuple[Any, ...]] = set()
    for row in kept:
        identity = tuple(row[k] for k in table.key)
        if identity in seen:
            raise InvariantViolated(table.name, f"duplicate key {identity}")
        seen.add(identity)
    return kept, rejected
