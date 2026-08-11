"""The daily line: how many jobs were open, how many were new, what the median was.

Computed over the whole history in one query rather than appended to, so a day
that was refused by the guards leaves a gap rather than a wrong point, and a
re-run of the aggregator over the same parquet produces the same series.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DayPoint", "timeseries"]

_SQL = """
    SELECT s.snapshot_date,
           count(*) AS active,
           sum(CASE WHEN j.first_seen = s.snapshot_date THEN 1 ELSE 0 END) AS new,
           median(s.salary_mid_usd) FILTER (s.has_salary AND NOT s.is_management) AS median_usd
    FROM snap s
    LEFT JOIN (SELECT job_uid, min(first_seen) first_seen FROM jobs GROUP BY 1) j USING(job_uid)
    GROUP BY 1 ORDER BY 1
"""


@dataclass(frozen=True)
class DayPoint:
    """One day on the chart."""

    date: str
    active: int
    new: int
    median_usd: int | None

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "active": self.active,
            "new": self.new,
            "median_usd": self.median_usd,
        }


def timeseries(con) -> list[DayPoint]:
    """Every day in the history, oldest first.

    ``new`` counts postings whose first sighting is this day. It is a left join
    because a snapshot row can outlive its jobs partition — the jobs table is
    written only when something is new — and an inner join would silently drop
    every day where nothing was.
    """
    return [
        DayPoint(
            date=str(date),
            active=int(active),
            new=int(new or 0),
            median_usd=round(median_usd) if median_usd is not None else None,
        )
        for date, active, new, median_usd in con.execute(_SQL).fetchall()
    ]
