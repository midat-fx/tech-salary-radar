"""Which board's copy of a job wins, and why the order is what it is.

When the same job appears twice, one row has to represent it. The choice is not
arbitrary: the boards carry different amounts of information, and picking the
poorer copy throws away a salary that was there.

The order is by how much each board states outright:

1. **Ashby** — structured compensation with currency, interval and tiers.
2. **Lever** — a compensation field, but form-filled and often incomplete.
3. **Greenhouse** — nothing structured; pay has to be read out of the ad, and
   most of the time it is not there at all.

Within a board, and as the tie-break across boards, the copy that actually has
a salary wins over one that does not. A rule that went by board alone would
prefer an Ashby posting with no pay over a Greenhouse one whose ad states a
range, which is backwards.
"""

from __future__ import annotations

__all__ = ["SOURCE_RANK", "rank_of", "better_of", "sort_candidates"]

#: Lower is better.
SOURCE_RANK = {"ashby": 0, "lever": 1, "greenhouse": 2}

#: A board nobody has ranked sorts last rather than raising: the seed is older
#: than the code and may name an ATS added since.
_UNKNOWN = len(SOURCE_RANK)


def rank_of(source: str | None) -> int:
    return SOURCE_RANK.get((source or "").lower(), _UNKNOWN)


def _key(row: dict) -> tuple:
    return (
        0 if row.get("has_salary") else 1,
        rank_of(row.get("source")),
        # Stable last resort so a tie does not depend on dict ordering: two runs
        # over the same day must pick the same winner.
        str(row.get("job_uid") or ""),
    )


def better_of(left: dict, right: dict) -> dict:
    """The row that should represent the job."""
    return left if _key(left) <= _key(right) else right


def sort_candidates(rows: list[dict]) -> list[dict]:
    """Best first. The head is the winner; the tail is what it absorbed."""
    return sorted(rows, key=_key)
