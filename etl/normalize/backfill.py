"""Rebuild the inflow table from each open posting's publish date.

A one-off, and it exists because the inflow view was wrong for the first days.
``first_seen`` was originally the day the crawl noticed a posting, which for
everything open on day one meant day one — a fabricated spike of six thousand
"new" jobs, followed by a series that had to be read around it.

The boards report when a posting went up, so the correct answer is recoverable.
It is a separate operation rather than part of the daily run: it rewrites every
partition in the jobs table, and something that rewrites history should be
something a person types.
"""

from __future__ import annotations

from etl.clock import parse_iso
from etl.normalize.columns import JOB_COLUMNS, project
from etl.normalize.rows import build_records

__all__ = ["publish_date", "backfill_job_rows"]


def publish_date(published_at) -> str | None:
    """The calendar day a posting went up, or ``None`` when unreadable."""
    parsed = parse_iso(published_at)
    return parsed.date().isoformat() if parsed else None


def backfill_job_rows(jobs, rates, today: str) -> dict[str, list[dict]]:
    """Group every open posting under the day it was published.

    A posting whose date cannot be read falls back to today rather than being
    dropped: it is a real open job, and losing it from the inflow view would
    trade one wrong answer for a missing one.
    """
    records, _ = build_records(jobs, rates, today)
    by_date: dict[str, list[dict]] = {}
    for record in records:
        first_seen = publish_date(record.get("published_at")) or today
        row = {**project(record, JOB_COLUMNS), "first_seen": first_seen}
        by_date.setdefault(first_seen, []).append(row)
    return by_date
