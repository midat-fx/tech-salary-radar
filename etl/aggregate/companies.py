"""Per-company pay, and the rule that decides which companies get a number.

The dashboard lists companies by how many openings they have, and shows a
median beside each. The count and the median need different minimums, and
conflating them is how a company with forty postings and three salaries gets a
headline figure resting on three people.

So a company appears in the list on its posting count and gets a *median* only
if enough of those postings state pay. Below the threshold it is listed with the
count and no figure, which says "we do not know" rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from etl.aggregate.meta import BOARD_URL

__all__ = ["CompanyStats", "MIN_SALARIES_FOR_MEDIAN", "TOP_N", "company_stats", "top_companies"]

#: A company needs this many salary-bearing postings before its median is shown.
#: Five is small, and it is chosen against the alternative of showing nothing:
#: most companies post two or three ranges, and a threshold of ten would empty
#: the column entirely.
MIN_SALARIES_FOR_MEDIAN = 5

#: How many companies reach the page.
TOP_N = 10

_SQL = """
    SELECT company,
           any_value(source)                                        AS source,
           count(*)                                                 AS n,
           count(*) FILTER (has_salary AND NOT is_management)       AS n_paid,
           median(salary_mid_usd) FILTER (has_salary AND NOT is_management) AS median_usd,
           count(*) FILTER (is_remote)                              AS n_remote
    FROM snap
    WHERE snapshot_date = ?
    GROUP BY 1
    ORDER BY n DESC, company
"""


@dataclass(frozen=True)
class CompanyStats:
    """One company's row on the page."""

    company: str
    source: str
    n: int
    n_paid: int
    median_usd: int | None
    n_remote: int

    @property
    def has_median(self) -> bool:
        return self.median_usd is not None

    @property
    def salary_share(self) -> float:
        return self.n_paid / self.n if self.n else 0.0

    @property
    def remote_share(self) -> float:
        return self.n_remote / self.n if self.n else 0.0

    @property
    def url(self) -> str:
        template = BOARD_URL.get(self.source)
        return template.format(slug=self.company) if template else ""

    def as_dict(self) -> dict:
        return {
            "company": self.company,
            "n": self.n,
            "url": self.url,
            "median_usd": self.median_usd,
            "n_paid": self.n_paid,
            "remote_share": round(self.remote_share, 2),
        }


def _median_or_none(n_paid: int, value) -> int | None:
    """A median only when enough postings backed it."""
    if value is None or n_paid < MIN_SALARIES_FOR_MEDIAN:
        return None
    return round(value)


def company_stats(con, latest_date) -> list[CompanyStats]:
    """Every company that had a posting open on ``latest_date``, biggest first."""
    rows = con.execute(_SQL, [latest_date]).fetchall()
    return [
        CompanyStats(
            company=company,
            source=source,
            n=int(n),
            n_paid=int(n_paid or 0),
            median_usd=_median_or_none(int(n_paid or 0), median_usd),
            n_remote=int(n_remote or 0),
        )
        for company, source, n, n_paid, median_usd, n_remote in rows
    ]


def top_companies(con, latest_date, limit: int = TOP_N) -> list[dict]:
    """The published shape: the biggest employers, in the order the page shows."""
    return [stats.as_dict() for stats in company_stats(con, latest_date)[:limit]]


def median_of(salaries: list[float], n_paid: int | None = None) -> int | None:
    """The same rule, for a caller that already has the figures in hand."""
    count = n_paid if n_paid is not None else len(salaries)
    if not salaries or count < MIN_SALARIES_FOR_MEDIAN:
        return None
    return round(median(salaries))
