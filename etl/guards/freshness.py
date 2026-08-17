"""Is what we are about to publish actually about today?

The volume guard asks whether enough rows arrived and the plausibility guard
whether they look like yesterday's. This one asks a third question that both
miss: whether the *inputs* were current. A run can produce a full, plausible day
entirely out of stale material — a rate table from last week, a snapshot date
that does not match the partition it is being written to, a crawl whose newest
posting is a month old because a board started serving a cached response.

None of these changes the row count, and none of them is visible in the rows
themselves without comparing them to the clock.
"""

from __future__ import annotations

from etl.clock import age_in_days
from etl.guards.verdict import Severity, Verdict

__all__ = ["MAX_FX_AGE_DAYS", "MAX_NEWEST_POSTING_AGE_DAYS", "check_freshness"]

#: Beyond this the rate table is old enough that every converted figure in the
#: day should be doubted. Matches the flag the site publishes.
MAX_FX_AGE_DAYS = 3

#: If the newest posting in a whole crawl is older than this, the boards are
#: serving something cached. Two weeks is generous: hiring genuinely stops over
#: the winter holidays.
MAX_NEWEST_POSTING_AGE_DAYS = 14


def check_freshness(rows: list[dict], day: str, fx_day: str | None, now) -> Verdict:
    """Compare the day's inputs against the clock the run was given."""
    verdict = Verdict()
    if not rows:
        return verdict

    fx_age = age_in_days(fx_day, now)
    if fx_age is None:
        verdict.add("freshness", Severity.WARN, "the rate table carries no date")
    elif fx_age > MAX_FX_AGE_DAYS:
        verdict.add(
            "freshness",
            Severity.WARN,
            f"the rate table is {fx_age} days old — every converted figure today is doubtful",
        )

    mismatched = {row.get("snapshot_date") for row in rows} - {day}
    if mismatched:
        # A row dated differently from the partition it is being written to
        # means the run's idea of today moved mid-flight.
        verdict.add(
            "freshness",
            Severity.REFUSE,
            f"rows dated {sorted(str(d) for d in mismatched)} in the partition for {day}",
        )

    published = [age_in_days(row.get("published_at"), now) for row in rows]
    known = [age for age in published if age is not None]
    if known and min(known) > MAX_NEWEST_POSTING_AGE_DAYS:
        verdict.add(
            "freshness",
            Severity.WARN,
            f"the newest posting in the crawl is {min(known)} days old — a board may be serving a cache",
        )
    return verdict
