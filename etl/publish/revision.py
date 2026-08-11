"""What happens when a day has to be published twice.

Days are written once by the cron and never touched again — that is the whole
point of an append-only history. But "never" has two exceptions that are real:
a day the guards refused and that is re-run the next morning, and a day whose
aggregation is rebuilt after a code change without the underlying parquet
moving at all.

The two want different answers, and conflating them is how a chart stops being
reproducible from a commit. A **rebuild** is expected and silent: the same
parquet through new code, and the published file changes because the code did.
A **revision** means the day's own data changed after it was first published,
which is the case that has to leave a record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["Kind", "Revision", "classify"]


class Kind(str, Enum):
    FIRST = "first"
    """The day had not been published before."""

    REBUILD = "rebuild"
    """Same source data, new output. The code changed, the history did not."""

    REVISION = "revision"
    """The day's own data changed after publication. Recorded, not hidden."""

    UNCHANGED = "unchanged"
    """Byte-identical output. Worth printing: it means the run was a no-op."""


@dataclass(frozen=True)
class Revision:
    """One published day's provenance."""

    day: str
    kind: Kind
    detail: str = ""

    @property
    def needs_recording(self) -> bool:
        return self.kind is Kind.REVISION

    def describe(self) -> str:
        return f"{self.day}: {self.kind.value}" + (f" — {self.detail}" if self.detail else "")


def classify(
    day: str,
    published_before: bool,
    output_changed: bool,
    source_rows_changed: bool,
) -> Revision:
    """Name what this publication is."""
    if not published_before:
        return Revision(day, Kind.FIRST)
    if source_rows_changed:
        return Revision(day, Kind.REVISION, "the day's rows changed after it was first published")
    if output_changed:
        return Revision(day, Kind.REBUILD, "same rows, different output — the code changed")
    return Revision(day, Kind.UNCHANGED)
