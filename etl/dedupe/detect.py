"""Find the groups, apply the merge, and report what it cost.

The report is not decoration. De-duplication changes the two numbers the site
leads with — jobs tracked and the median — so a run where the duplicate count
moves sharply is either a board changing its slugs or this layer merging things
it should not. Both need to be visible the next morning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etl.dedupe.fingerprint import Fingerprint, fingerprint
from etl.dedupe.merge import MergedJob, merge_group

__all__ = ["DedupeReport", "group_by_fingerprint", "deduplicate"]


@dataclass
class DedupeReport:
    """What a day's de-duplication did."""

    rows_in: int = 0
    rows_out: int = 0
    groups_merged: int = 0
    duplicates_removed: int = 0
    fields_filled: int = 0
    unusable_keys: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def duplicate_share(self) -> float:
        return self.duplicates_removed / self.rows_in if self.rows_in else 0.0

    def describe(self) -> str:
        return (
            f"dedupe: {self.rows_in} -> {self.rows_out} rows"
            f" ({self.duplicates_removed} cross-board duplicates in {self.groups_merged} groups,"
            f" {self.fields_filled} fields filled from the losing copy,"
            f" {self.unusable_keys} rows left alone)"
        )


def group_by_fingerprint(rows: list[dict]) -> tuple[dict[Fingerprint, list[dict]], list[dict]]:
    """Split rows into fingerprint groups and the ones that cannot be keyed.

    A posting with no company or no title is returned untouched rather than
    grouped: without those two the fingerprint identifies nothing, and merging
    on it would collapse every broken posting into one.
    """
    groups: dict[Fingerprint, list[dict]] = {}
    unusable: list[dict] = []
    for row in rows:
        key = fingerprint(row)
        if not key.is_usable:
            unusable.append(row)
            continue
        groups.setdefault(key, []).append(row)
    return groups, unusable


def deduplicate(rows: list[dict], max_examples: int = 5) -> tuple[list[dict], DedupeReport]:
    """One row per job. Order is by fingerprint, so two runs agree exactly."""
    report = DedupeReport(rows_in=len(rows))
    groups, unusable = group_by_fingerprint(rows)
    report.unusable_keys = len(unusable)

    merged: list[MergedJob] = []
    for key in sorted(groups, key=str):
        result = merge_group(groups[key])
        merged.append(result)
        if result.is_merged:
            report.groups_merged += 1
            report.duplicates_removed += len(result.duplicates)
            report.fields_filled += len(result.filled)
            if len(report.examples) < max_examples:
                report.examples.append(f"{key} <- {', '.join(result.duplicates)}")

    out = [m.row for m in merged] + unusable
    report.rows_out = len(out)
    return out, report
