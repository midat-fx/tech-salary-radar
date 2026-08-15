"""The rate table, and what it is allowed to claim about itself.

Rates are quoted as **units per one USD** throughout — the shape both upstream
sources use, and the shape the conversion divides by. Storing them the other way
round would be equally valid and would make every conversion in the pipeline a
multiplication instead; what matters is that only one convention exists, because
the two are indistinguishable at a glance and differ by a factor of a thousand
on JPY.
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.clock import age_in_days
from etl.config import FX_MAX_AGE_DAYS

__all__ = ["RateTable", "MAX_AGE_DAYS"]

MAX_AGE_DAYS = FX_MAX_AGE_DAYS


@dataclass(frozen=True)
class RateTable:
    """Units per one USD, the day they were fetched, and where from."""

    rates: dict[str, float]
    day: str | None = None
    source: str = "unknown"

    def __post_init__(self) -> None:
        # USD against itself is not something a source needs to state, and a
        # source that states it wrongly would silently rescale every US salary.
        object.__setattr__(self, "rates", {**self.rates, "USD": 1.0})

    def __contains__(self, code: str) -> bool:
        return code.upper() in self.rates

    def get(self, code: str | None) -> float | None:
        return self.rates.get((code or "USD").upper())

    def age(self, now) -> int | None:
        return age_in_days(self.day, now)

    def is_stale(self, now, max_age: int = MAX_AGE_DAYS) -> bool:
        """True when the table is old enough that its figures should be doubted.

        A table with no date is stale by definition: every non-USD figure in the
        day was converted with *something*, and the page should say the rate is
        unknown rather than imply it was current.
        """
        age = self.age(now)
        return age is None or age > max_age

    def describe(self, now=None) -> str:
        known = ", ".join(sorted(code for code in self.rates if code != "USD")) or "none"
        when = self.day or "undated"
        stale = " (stale)" if now is not None and self.is_stale(now) else ""
        return f"fx {when} from {self.source}{stale}: {known}"
