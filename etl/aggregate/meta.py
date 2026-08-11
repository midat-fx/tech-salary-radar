"""Everything the page says about itself: coverage, freshness, and the caveats.

This is where the site admits what it does not know. The salary share, the
labelled share, the FX age and the dropped-row counts are all published beside
the numbers they qualify, because a median over 22% of postings is a different
claim from a median over all of them, and the reader cannot tell which they are
looking at unless it says.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from etl.clock import age_in_days, iso_second
from etl.config import FX_MAX_AGE_DAYS

__all__ = ["FxStatus", "Coverage", "BOARD_URL", "SALARY_NOTE", "ATTRIBUTION", "read_fx", "coverage_of"]

BOARD_URL = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
}

SALARY_NOTE = (
    "Зарплаты — gross, годовые, как принято в международном найме; в USD "
    "(не-USD → USD по дневному курсу). По N вакансий с указанной вилкой."
)
ATTRIBUTION = (
    "Данные о вакансиях: публичные карьерные доски компаний "
    "(Greenhouse, Lever, Ashby). Проект не аффилирован с ними."
)


@dataclass(frozen=True)
class FxStatus:
    """The rate table's age, and whether it is old enough to distrust."""

    date: str | None
    stale: bool
    gbp_usd: float | None
    eur_usd: float | None
    source: str = "er-api"
    base: str = "USD"

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "base": self.base,
            "source": self.source,
            "stale": self.stale,
            "gbp_usd": self.gbp_usd,
            "eur_usd": self.eur_usd,
        }


def read_fx(data_dir: str | Path, now) -> FxStatus:
    """The cached rate table, judged against the clock the run was given.

    A missing cache is stale rather than absent: every non-USD figure in the day
    was converted with *something*, and the page should say the rate is unknown
    rather than imply it was current.
    """
    path = Path(data_dir) / "cache" / "fx_latest.json"
    if not path.exists():
        return FxStatus(None, True, None, None)
    raw = json.loads(path.read_text())
    rates = raw.get("rates", {})
    age = age_in_days(raw.get("date"), now)
    return FxStatus(
        date=raw.get("date"),
        stale=age is None or age > FX_MAX_AGE_DAYS,
        gbp_usd=round(1 / rates["GBP"], 4) if rates.get("GBP") else None,
        eur_usd=round(1 / rates["EUR"], 4) if rates.get("EUR") else None,
    )


@dataclass(frozen=True)
class Coverage:
    """What share of the day the headline numbers actually rest on."""

    salary_share: float
    skills_extracted_share: float
    dropped_salary_out_of_bounds: int
    filtered_non_tech: int

    def as_dict(self) -> dict:
        return {
            "salary_share": self.salary_share,
            "skills_extracted_share": self.skills_extracted_share,
            "dropped_salary_out_of_bounds": self.dropped_salary_out_of_bounds,
            "filtered_non_tech": self.filtered_non_tech,
        }


def coverage_of(with_salary: int, processed: int, total: int, last_run: dict) -> Coverage:
    """Shares rounded to three places; a zero day divides to zero, not an error."""
    return Coverage(
        salary_share=round(with_salary / total, 3) if total else 0.0,
        skills_extracted_share=round(processed / total, 3) if total else 0.0,
        dropped_salary_out_of_bounds=int(last_run.get("dropped_oob", 0)),
        filtered_non_tech=int(last_run.get("filtered_non_tech", 0)),
    )


def stamp(now) -> str:
    """The ``updated_at`` every published file carries."""
    return iso_second(now)
