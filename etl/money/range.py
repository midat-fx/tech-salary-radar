"""A posted pay range, and the one number the statistics are built on.

Every downstream figure — the market median, each skill premium, every
confidence interval — is a median of midpoints. So the midpoint rule is not a
formatting detail; it decides what the site means by "salary". ADR 0002 records
why it is ``COALESCE((min+max)/2, min, max)`` and not a mean of anything.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from etl.money.currency import Confidence, CurrencyGuess
from etl.money.interval import Interval, to_annual

__all__ = ["PayRange", "midpoint"]


def midpoint(low: float | None, high: float | None) -> float | None:
    """The single figure a range contributes: the mean of the bounds it has.

    A one-sided range is common and meaningful — "from $180,000" is a floor the
    employer committed to — so it contributes that bound rather than nothing.
    Averaging it with a made-up other end would invent precision; dropping it
    would throw away the most informative postings, since one-sided ranges skew
    senior.
    """
    if low is not None and high is not None:
        return (low + high) / 2
    if low is not None:
        return float(low)
    if high is not None:
        return float(high)
    return None


@dataclass(frozen=True)
class PayRange:
    """What a board said about pay, before any judgement about whether to believe it."""

    low: float | None
    high: float | None
    currency: CurrencyGuess
    interval: Interval
    #: Where it came from: a structured field, an anchored text match, a summary
    #: string. Carried so the run report can say which parser is producing what.
    origin: str = "unknown"

    def __post_init__(self) -> None:
        low, high = self.low, self.high
        if low is not None and high is not None and low > high:
            # Lever sends the pair straight from a form, and forms get filled in
            # backwards. Swapping is right: the two numbers are a range, and
            # which cell they were typed into is not information. Storing them
            # inverted instead fails the writer's invariant and costs the row.
            object.__setattr__(self, "low", high)
            object.__setattr__(self, "high", low)

    @property
    def is_empty(self) -> bool:
        return self.low is None and self.high is None

    @property
    def is_one_sided(self) -> bool:
        return not self.is_empty and (self.low is None or self.high is None)

    @property
    def spread(self) -> float | None:
        """``high / low``. A range wider than a few times is usually not one range."""
        if self.low and self.high and self.low > 0:
            return self.high / self.low
        return None

    def midpoint(self) -> float | None:
        return midpoint(self.low, self.high)

    def annualised(self) -> "PayRange":
        """The same range expressed yearly. Idempotent once the interval is a year."""
        if self.interval is Interval.YEAR:
            return self
        return replace(
            self,
            low=to_annual(self.low, self.interval),
            high=to_annual(self.high, self.interval),
            interval=Interval.YEAR,
        )

    def with_currency(self, code: str, confidence: Confidence) -> "PayRange":
        return replace(self, currency=CurrencyGuess(code, confidence))

    def describe(self) -> str:
        """One line for the run report and for a failing test's message."""
        low = "-" if self.low is None else f"{self.low:,.0f}"
        high = "-" if self.high is None else f"{self.high:,.0f}"
        return (
            f"{low}..{high} {self.currency.code}/{self.interval.value} "
            f"({self.currency.confidence.value}, {self.origin})"
        )
