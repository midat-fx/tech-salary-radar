"""Refuse a day whose numbers say a source collapsed rather than the market did.

The history is append-only and committed. A day written while Greenhouse was
returning 500s records a two-thirds fall in the tech job market that never
happened, and the timeseries never recovers from it — there is no later run that
goes back and fixes an earlier day.

So the comparison is against the recent past, per source, and the answer is to
write nothing rather than to write something wrong.
"""

from __future__ import annotations

from pathlib import Path
from statistics import median

from etl.guards.verdict import Severity, Verdict

__all__ = [
    "MIN_HISTORY_DAYS",
    "SOURCE_FLOOR",
    "TOTAL_FLOOR",
    "WINDOW_DAYS",
    "check_volume",
    "source_medians",
]

#: Fewer days than this and there is nothing to compare against. The launch week
#: must not be blocked by a guard that has no history yet.
MIN_HISTORY_DAYS = 3

#: How many recent days form the comparison. A week absorbs the weekday shape of
#: job posting without absorbing a month-long trend.
WINDOW_DAYS = 7

#: A source must keep at least half of its recent median...
SOURCE_FLOOR = 0.5
#: ...and the day as a whole at least three fifths of the expected total. The
#: second catches the case the first cannot: every source down by forty per
#: cent, each individually inside its floor.
TOTAL_FLOOR = 0.6


def source_medians(data_dir: str | Path, exclude_dt: str, window: int = WINDOW_DAYS):
    """Recent per-source row counts -> {source: median}. Empty when history is short."""
    root = Path(data_dir) / "snapshots"
    parts = [p for p in root.glob("dt=*/part.parquet") if p.parent.name != f"dt={exclude_dt}"]
    if len(parts) < MIN_HISTORY_DAYS:
        return {}
    import duckdb

    files = ",".join(f"'{p}'" for p in parts)
    rows = duckdb.sql(
        f"SELECT source, snapshot_date, count(*) FROM read_parquet([{files}]) "
        "GROUP BY 1,2 ORDER BY 2 DESC"
    ).fetchall()
    history: dict[str, list[int]] = {}
    for source, _day, count in rows:
        history.setdefault(source, []).append(count)
    return {source: median(counts[:window]) for source, counts in history.items()}


def check_volume(data_dir: str | Path, dt: str, by_source: dict[str, int]) -> Verdict:
    """Compare today against the recent median, per source and in total."""
    verdict = Verdict()
    medians = source_medians(data_dir, dt)
    if not medians:
        return verdict

    expected_total = 0.0
    for source, expected in medians.items():
        expected_total += expected
        got = by_source.get(source, 0)
        if got < SOURCE_FLOOR * expected:
            verdict.add(
                "volume",
                Severity.REFUSE,
                f"{source}: {got} rows against a {WINDOW_DAYS}-day median of {expected:.0f}",
            )

    got_total = sum(by_source.values())
    if expected_total and got_total < TOTAL_FLOOR * expected_total:
        verdict.add(
            "volume",
            Severity.REFUSE,
            f"total: {got_total} rows against an expected ~{expected_total:.0f}",
        )

    # A source that appears from nowhere is not a reason to refuse, but it is
    # worth saying: it means the seed grew, or a board changed its shape.
    for source in by_source:
        if source not in medians:
            verdict.add("volume", Severity.WARN, f"{source}: no recent history to compare against")
    return verdict
