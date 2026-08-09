"""Combine the copies of one job into the row that represents it.

Picking a winner is not enough. The losing copy often knows something the
winner does not — a Greenhouse ad that states a range next to an Ashby posting
that left compensation empty — and discarding it loses real information about
the market.

So the winner's identity is kept whole, and only *absent* fields are filled
from the copies behind it. Nothing already stated is overwritten: a
disagreement between two boards about the same job is not something this layer
can resolve, and quietly preferring one side would make the published figure
depend on the merge order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etl.dedupe.priority import sort_candidates

__all__ = ["MergedJob", "merge_group", "FILLABLE", "IDENTITY"]

#: Fields a losing copy may contribute when the winner has none.
FILLABLE = (
    "salary_min_usd",
    "salary_max_usd",
    "salary_mid_usd",
    "employment_type",
    "published_at",
    "apply_url",
    "currency_original",
    "salary_min_orig",
    "salary_max_orig",
    "salary_interval_orig",
)

#: Fields that identify the winning posting and are never taken from a loser.
IDENTITY = ("job_uid", "source", "company", "snapshot_date", "region", "seniority")


@dataclass
class MergedJob:
    """One job, the posting chosen to represent it, and what it absorbed."""

    row: dict
    duplicates: tuple[str, ...] = ()
    filled: tuple[str, ...] = field(default=())

    @property
    def is_merged(self) -> bool:
        return bool(self.duplicates)


def merge_group(rows: list[dict]) -> MergedJob:
    """Reduce the copies of one job to a single row.

    ``has_salary`` is recomputed rather than copied: filling a salary from a
    losing copy without setting the flag would store a figure the dashboard
    filters out, and setting the flag without a figure fails the writer.
    """
    if len(rows) == 1:
        return MergedJob(dict(rows[0]))

    ordered = sort_candidates(rows)
    winner, losers = dict(ordered[0]), ordered[1:]
    filled: list[str] = []
    for field_name in FILLABLE:
        if winner.get(field_name) is not None:
            continue
        for loser in losers:
            value = loser.get(field_name)
            if value is not None:
                winner[field_name] = value
                filled.append(field_name)
                break
    if "has_salary" in winner:
        winner["has_salary"] = winner.get("salary_mid_usd") is not None
    return MergedJob(
        row=winner,
        duplicates=tuple(str(loser.get("job_uid")) for loser in losers),
        filled=tuple(filled),
    )
