"""Day-level checks on what the numbers say about themselves.

The volume guard asks whether enough rows arrived. These ask whether the rows
that did arrive look like the same pipeline that ran yesterday. They catch the
failures that keep the count intact while changing what the count means: a
parser that stopped finding salaries, a currency table that went stale, a
region rule that started sending everything to ``other``.

None of them refuses on its own. A shift in any one of them is a strong signal
and a weak proof, and refusing a day on a warning would mean losing real data
the first time the market did something unusual.
"""

from __future__ import annotations

from etl.guards.verdict import Severity, Verdict

__all__ = [
    "MIN_SALARY_SHARE",
    "MAX_OTHER_REGION_SHARE",
    "MAX_UNSPECIFIED_SHARE",
    "check_plausibility",
    "share",
]

#: Below this share of rows carrying a salary, the parser is more likely broken
#: than the market suddenly private. Observed range is 18–24%.
MIN_SALARY_SHARE = 0.08

#: Above this share landing in ``other``, the region tables stopped matching.
MAX_OTHER_REGION_SHARE = 0.75

#: Above this share of ``unspecified`` seniority, the title rules stopped firing.
MAX_UNSPECIFIED_SHARE = 0.85


def share(count: int, total: int) -> float:
    return count / total if total else 0.0


def check_plausibility(rows: list[dict]) -> Verdict:
    """Look at one day's rows as a population rather than one at a time."""
    verdict = Verdict()
    total = len(rows)
    if not total:
        return verdict.add("plausibility", Severity.REFUSE, "the day has no rows at all")

    with_salary = share(sum(1 for r in rows if r.get("has_salary")), total)
    if with_salary < MIN_SALARY_SHARE:
        verdict.add(
            "plausibility",
            Severity.WARN,
            f"only {with_salary:.1%} of rows carry a salary (expected above {MIN_SALARY_SHARE:.0%})",
        )

    other = share(sum(1 for r in rows if r.get("region") == "other"), total)
    if other > MAX_OTHER_REGION_SHARE:
        verdict.add(
            "plausibility",
            Severity.WARN,
            f"{other:.1%} of rows have no recognised region — the place tables may have stopped matching",
        )

    unspecified = share(sum(1 for r in rows if r.get("seniority") == "unspecified"), total)
    if unspecified > MAX_UNSPECIFIED_SHARE:
        verdict.add(
            "plausibility",
            Severity.WARN,
            f"{unspecified:.1%} of titles read as unspecified — the level rules may have stopped firing",
        )

    sources = {r.get("source") for r in rows}
    if len(sources) == 1 and total > 100:
        verdict.add(
            "plausibility",
            Severity.WARN,
            f"every row came from {next(iter(sources))!r} — the other boards contributed nothing",
        )
    return verdict
