"""Which postings get the day's labelling budget, and in what order.

The budget is finite — the free tier allows about 900 calls a day, which at ten
postings a call is five thousand jobs against a crawl that returns six and a
half thousand. So this is a real allocation problem, and getting it wrong is
invisible: the coverage number still goes up, just on the postings that matter
least.

Three rules, in order:

1. **Never-labelled before re-extraction.** A prompt upgrade must not stall
   coverage of new postings while it re-does old ones.
2. **Salary-bearing first.** The skill premium — the site's flagship number —
   can only use postings that have a salary. A labelled posting with no salary
   contributes to coverage and to nothing else.
3. **Newest first, then round-robin by source.** Greenhouse is two thirds of the
   crawl; without the round-robin it takes two thirds of the budget and the
   other boards are never labelled at all.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Candidate", "prioritise", "sort_key"]


@dataclass(frozen=True)
class Candidate:
    """A posting waiting for a label, with the facts that decide its place."""

    uid: str
    job: dict
    has_salary: bool = False
    published_at: str = ""
    is_stale: bool = False
    """Already labelled, but by an older prompt. Re-extractable, not urgent."""

    @property
    def source(self) -> str:
        return self.job.get("source", "")


def _newest_first(published: str) -> tuple[int, ...]:
    """Sort key that puts the newest ISO timestamp first.

    Negating the code points rather than reversing the sort keeps this key
    composable with the two ahead of it, which have to stay ascending.
    """
    return tuple(-ord(char) for char in (published or ""))


def sort_key(candidate: Candidate) -> tuple:
    return (
        1 if candidate.is_stale else 0,
        0 if candidate.has_salary else 1,
        _newest_first(candidate.published_at),
    )


def prioritise(candidates: list[Candidate], limit: int | None = None) -> list[Candidate]:
    """Order by the three rules, then interleave sources, then apply the budget."""
    ordered = sorted(candidates, key=sort_key)
    buckets: dict[str, list[Candidate]] = {}
    for candidate in ordered:
        buckets.setdefault(candidate.source, []).append(candidate)
    interleaved: list[Candidate] = []
    while any(buckets.values()):
        for source in list(buckets):
            if buckets[source]:
                interleaved.append(buckets[source].pop(0))
    return interleaved[:limit] if limit is not None else interleaved
