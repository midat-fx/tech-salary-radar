"""What each stored table actually contains — the writer's promise, in one place.

The column lists used to live as two bare tuples inside ``normalize.py``, next
to the code that built rows from them. That worked while there was one writer.
It stopped working once the aggregator, the backfill and the skills cache all
read the same parquet: nothing stated which columns were required, which could
be null, or what an absent one should be read as, so every reader invented its
own answer and DuckDB's NULL-fill made the disagreements invisible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etl.schema.version import SchemaVersion

__all__ = ["Field", "Table", "SNAPSHOTS", "JOBS", "SKILLS", "TABLES", "table_for"]


@dataclass(frozen=True)
class Field:
    """One column: its type, whether it may be null, and what an absent one means."""

    name: str
    kind: type
    #: Null is a value the column may legitimately hold — a job with no posted
    #: salary really has no salary, and storing 0 would be a lie.
    nullable: bool = True
    #: What a reader substitutes when the column is missing entirely because the
    #: partition predates it. Distinct from ``nullable``: absent means "this day
    #: could not have known", null means "this row does not have one".
    default: Any = None
    #: The minor version that introduced the column. A reader uses it to explain
    #: a fill rather than merely performing one.
    since: SchemaVersion = field(default=SchemaVersion(1, 0))
    doc: str = ""


@dataclass(frozen=True)
class Table:
    """A stored table: its columns, its key, and how a partition is ordered."""

    name: str
    fields: tuple[Field, ...]
    #: Columns whose combination identifies a row inside one partition.
    key: tuple[str, ...]
    #: The column a partition is sorted by before writing. Canonical order makes
    #: a rewritten day byte-identical when the data has not changed, which is
    #: what lets a data commit be trusted as evidence that something changed.
    sort_by: str

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if not f.nullable)

    def field(self, name: str) -> Field | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def defaults(self) -> dict[str, Any]:
        """Column -> value to use when a partition predates the column."""
        return {f.name: f.default for f in self.fields}


_V10 = SchemaVersion(1, 0)
_V11 = SchemaVersion(1, 1)
_V12 = SchemaVersion(1, 2)

#: One row per job that was open on a given day. The active-market view.
SNAPSHOTS = Table(
    name="snapshots",
    key=("job_uid",),
    sort_by="job_uid",
    fields=(
        Field("job_uid", str, nullable=False, doc="source:company:job_id"),
        Field("snapshot_date", str, nullable=False, doc="the partition this row belongs to"),
        Field("source", str, nullable=False, doc="greenhouse | lever | ashby"),
        Field("company", str, nullable=False, doc="board slug"),
        Field("region", str, nullable=False, default="other", doc="us | eu | other"),
        Field("is_remote", bool, nullable=False, default=False),
        Field("seniority", str, nullable=False, default="unspecified"),
        Field("is_management", bool, nullable=False, default=False),
        Field("salary_min_usd", float, doc="annual gross, converted"),
        Field("salary_max_usd", float),
        Field("salary_mid_usd", float, doc="COALESCE((min+max)/2, min, max) — see ADR 0002"),
        Field("has_salary", bool, nullable=False, default=False),
        Field("employment_type", str),
        Field("published_at", str, doc="ISO-8601 as the board reported it"),
    ),
)

#: One row per job the first time it was seen. The inflow view.
JOBS = Table(
    name="jobs",
    key=("job_uid",),
    sort_by="job_uid",
    fields=(
        Field("job_uid", str, nullable=False),
        Field("first_seen", str, nullable=False, doc="publish date when known, else run date"),
        Field("source", str, nullable=False),
        Field("company", str, nullable=False),
        Field("title", str, nullable=False, default=""),
        Field("location_raw", str, default=""),
        Field("region", str, nullable=False, default="other"),
        Field("is_remote", bool, nullable=False, default=False),
        Field("seniority", str, nullable=False, default="unspecified"),
        Field("is_management", bool, nullable=False, default=False),
        Field("employment_type", str),
        Field("published_at", str),
        Field("apply_url", str),
        Field("currency_original", str, since=_V11, doc="what the board actually quoted"),
        Field("salary_min_orig", float, since=_V11),
        Field("salary_max_orig", float, since=_V11),
        Field("salary_interval_orig", str, since=_V11, default="year"),
        Field("salary_min_usd", float),
        Field("salary_max_usd", float),
        Field("salary_mid_usd", float),
        Field("has_salary", bool, nullable=False, default=False),
    ),
)

#: One row per (job, skill). A job the model processed with no skills gets one
#: row with a null skill — that is how "labelled, found nothing" is told apart
#: from "never labelled", which ADR 0003 turns into a statistical rule.
SKILLS = Table(
    name="skills",
    key=("job_uid", "skill"),
    sort_by="job_uid",
    fields=(
        Field("job_uid", str, nullable=False),
        Field("skill", str, doc="canonical name, or null for a processed-but-empty job"),
        Field("source", str, nullable=False, default="llm"),
        Field("prompt_version", str, nullable=False, default="v1", since=_V12),
        Field("extracted_at", str, nullable=False, doc="ISO-8601 second precision"),
    ),
)

TABLES: dict[str, Table] = {t.name: t for t in (SNAPSHOTS, JOBS, SKILLS)}


def table_for(name: str) -> Table:
    """Look up a table by the directory it is stored under."""
    try:
        return TABLES[name]
    except KeyError:
        raise KeyError(f"unknown table {name!r}; known: {sorted(TABLES)}") from None
