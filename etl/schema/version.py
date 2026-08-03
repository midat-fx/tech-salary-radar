"""Snapshot schema versions, and what reading an older day is allowed to mean.

A month of parquet is already not homogeneous: ``salary_min_orig`` and the
per-currency columns arrived after the first week, ``prompt_version`` after the
second. Today the aggregator reads all of it with one query and gets away with
it because DuckDB fills an absent column with NULL — which is to say the
behaviour is an accident of the reader, not a promise of the writer.

This module makes it a promise. Every partition records the version it was
written with; a reader states the version it understands; and the pair decides
whether the day is readable, readable with defaults, or refused. See ADR 0008.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SCHEMA_VERSION",
    "SchemaVersion",
    "Compatibility",
    "HISTORY",
    "compatibility",
    "describe",
    "is_readable",
]


@dataclass(frozen=True, order=True)
class SchemaVersion:
    """A major.minor pair, ordered so ranges can be expressed as comparisons.

    Major changes the meaning of a column that already existed; minor only adds
    columns. That distinction is the whole compatibility rule — see
    :func:`compatibility`.
    """

    major: int
    minor: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    @classmethod
    def parse(cls, raw: str | None) -> "SchemaVersion | None":
        """``"1.2"`` -> ``SchemaVersion(1, 2)``; ``None`` for anything unparseable.

        Unparseable rather than raising: a partition written before versions
        existed carries no marker at all, and that is a known, handled state
        (see :data:`ASSUMED_FOR_UNMARKED`).
        """
        if not raw:
            return None
        parts = str(raw).strip().split(".")
        if len(parts) != 2:
            return None
        try:
            return cls(int(parts[0]), int(parts[1]))
        except ValueError:
            return None


#: What the writer stamps onto every partition it creates today.
SCHEMA_VERSION = SchemaVersion(1, 3)

#: Partitions written before versioning existed are read as this.
#: They are the first days of the project; they have the 1.0 column set.
ASSUMED_FOR_UNMARKED = SchemaVersion(1, 0)

#: Why each version exists, oldest first. This is the changelog a reader needs
#: in order to know what a missing column means for a given day.
HISTORY: dict[SchemaVersion, str] = {
    SchemaVersion(1, 0): "first snapshots: uid, date, source, company, region, seniority, salary",
    SchemaVersion(1, 1): "added original currency and the pre-conversion salary bounds",
    SchemaVersion(1, 2): "added prompt_version to skill rows so label generations do not mix",
    SchemaVersion(1, 3): "added the schema marker itself, plus the run revision",
}


class Compatibility:
    """The three answers a version pair can produce."""

    EXACT = "exact"
    """Same version. Every column is present and means what the reader expects."""

    OLDER_FILL_DEFAULTS = "older-fill-defaults"
    """Older minor of the same major: columns added since are filled with their
    declared defaults. This is the ordinary case for any day older than a week."""

    NEWER_IGNORE_EXTRA = "newer-ignore-extra"
    """Newer minor of the same major, i.e. a partition written by a deploy that
    has since been rolled back. Extra columns are ignored rather than refused:
    the shared columns still mean the same thing, which is what minor promises."""

    INCOMPATIBLE = "incompatible"
    """Different major. A column that already existed changed meaning, so
    reading the day with today's code would produce a plausible wrong number —
    the one failure mode worth refusing outright."""


def compatibility(written: SchemaVersion | None, reader: SchemaVersion = SCHEMA_VERSION) -> str:
    """How ``reader`` may treat a partition written with ``written``."""
    if written is None:
        written = ASSUMED_FOR_UNMARKED
    if written.major != reader.major:
        return Compatibility.INCOMPATIBLE
    if written.minor == reader.minor:
        return Compatibility.EXACT
    return (
        Compatibility.OLDER_FILL_DEFAULTS
        if written.minor < reader.minor
        else Compatibility.NEWER_IGNORE_EXTRA
    )


def is_readable(written: SchemaVersion | None, reader: SchemaVersion = SCHEMA_VERSION) -> bool:
    """True unless the major differs — the only case that must not be guessed at."""
    return compatibility(written, reader) != Compatibility.INCOMPATIBLE


def describe(written: SchemaVersion | None, reader: SchemaVersion = SCHEMA_VERSION) -> str:
    """One line for the run report: what will happen to this day and why."""
    verdict = compatibility(written, reader)
    stamped = "unmarked" if written is None else str(written)
    if verdict == Compatibility.EXACT:
        return f"schema {stamped}: exact match"
    if verdict == Compatibility.OLDER_FILL_DEFAULTS:
        return f"schema {stamped} < {reader}: columns added since are filled with defaults"
    if verdict == Compatibility.NEWER_IGNORE_EXTRA:
        return f"schema {stamped} > {reader}: columns added since are ignored"
    return f"schema {stamped} vs {reader}: incompatible major, refusing to read"
