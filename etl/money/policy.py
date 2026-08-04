"""Whether to believe a parsed range, and why a rejected one was rejected.

The thresholds used to be spread across three functions with two different
answers to the same question: one place required a spread of at most 3x, another
dropped only above 20x, and the floor was 20,000 in the parser but 10,000 in the
config. A posting could therefore be rejected or kept depending on which board
it came from rather than on what it said.

They live here now, as one ordered set of rules, each returning the reason it
fired. The reason is the point: a run that drops four hundred ranges should be
able to say whether they were bonuses, equity, hourly rates read as salaries, or
one board changing its format.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from etl.config import SALARY_MAX_USD, SALARY_MIN_USD
from etl.money.currency import Confidence
from etl.money.range import PayRange

__all__ = [
    "Verdict",
    "Judgement",
    "MAX_SPREAD",
    "MAX_SPREAD_ONE_SIDED",
    "PRE_CONVERSION_FLOOR",
    "judge_parsed",
    "judge_annual_usd",
]


class Verdict(str, Enum):
    """Why a range was kept or dropped. Every value is a counter in the run report."""

    ACCEPTED = "accepted"
    EMPTY = "empty"
    """Nothing was parsed at all — the ordinary case, most postings have no range."""
    UNSUPPORTED_CURRENCY = "unsupported-currency"
    """A real figure in a currency with no rate. Excluded rather than guessed at."""
    IMPLAUSIBLE_SPREAD = "implausible-spread"
    """``high/low`` too wide to be one range: usually a salary paired with equity."""
    BELOW_FLOOR = "below-floor"
    """Under the annual floor: a per-hour rate read as a year, or a stipend."""
    ABOVE_CEILING = "above-ceiling"
    """Over the ceiling: a funding round or a total-contract value."""
    NON_POSITIVE = "non-positive"
    """Zero or negative. Boards do send ``0 - 0`` for "not disclosed"."""


@dataclass(frozen=True)
class Judgement:
    """A verdict plus the sentence that explains it."""

    verdict: Verdict
    detail: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict is Verdict.ACCEPTED

    def __bool__(self) -> bool:
        return self.accepted


#: A two-sided band wider than this is not one band. Levels.fyi-style postings
#: that pair base with total compensation land here, and so does a salary
#: accidentally matched against an equity figure.
MAX_SPREAD = 4.0

#: The pre-conversion floor, applied in the posted currency before any FX. It
#: exists to catch hourly rates that were read as annual figures — "$75 - $95"
#: is a plausible hourly range and an absurd yearly one.
PRE_CONVERSION_FLOOR = 1_000.0

#: A one-sided range has no spread to check, so it gets the ordinary bounds only.
MAX_SPREAD_ONE_SIDED = float("inf")


def judge_parsed(parsed: PayRange | None) -> Judgement:
    """Rules that apply before conversion, in the currency the board quoted."""
    if parsed is None or parsed.is_empty:
        return Judgement(Verdict.EMPTY)

    for bound in (parsed.low, parsed.high):
        if bound is not None and bound <= 0:
            return Judgement(Verdict.NON_POSITIVE, parsed.describe())

    if not parsed.currency.is_supported:
        return Judgement(
            Verdict.UNSUPPORTED_CURRENCY,
            f"{parsed.currency.code} has no rate; {parsed.describe()}",
        )

    spread = parsed.spread
    limit = MAX_SPREAD_ONE_SIDED if parsed.is_one_sided else MAX_SPREAD
    if spread is not None and spread > limit:
        return Judgement(Verdict.IMPLAUSIBLE_SPREAD, f"spread {spread:.1f}x; {parsed.describe()}")

    annual = parsed.annualised()
    for bound in (annual.low, annual.high):
        if bound is not None and bound < PRE_CONVERSION_FLOOR:
            return Judgement(
                Verdict.BELOW_FLOOR,
                f"annualises to {bound:,.0f} {parsed.currency.code}; {parsed.describe()}",
            )
    return Judgement(Verdict.ACCEPTED)


def judge_annual_usd(midpoint: float | None, low: float | None, high: float | None) -> Judgement:
    """Rules that apply after conversion, on the figure that will be published."""
    if midpoint is None:
        return Judgement(Verdict.EMPTY)
    if midpoint <= 0:
        return Judgement(Verdict.NON_POSITIVE, f"{midpoint}")
    if low is not None and high is not None and low > 0 and high / low > MAX_SPREAD:
        # Survives this far only when the two bounds were converted at different
        # rates, i.e. the currencies were mixed somewhere upstream.
        return Judgement(Verdict.IMPLAUSIBLE_SPREAD, f"post-conversion spread {high / low:.1f}x")
    if midpoint < SALARY_MIN_USD:
        return Judgement(Verdict.BELOW_FLOOR, f"{midpoint:,.0f} USD below {SALARY_MIN_USD:,}")
    if midpoint > SALARY_MAX_USD:
        return Judgement(Verdict.ABOVE_CEILING, f"{midpoint:,.0f} USD above {SALARY_MAX_USD:,}")
    return Judgement(Verdict.ACCEPTED)


def confidence_penalty(parsed: PayRange) -> bool:
    """True when a range should be treated as weaker evidence than its face value.

    An assumed currency on a non-US board is the case this exists for: the
    figure is real, the unit is a guess, and the guess is systematically wrong
    in one direction. The caller decides what to do about it; today nothing
    does, and that inaction is recorded in ADR 0001 rather than left implicit.
    """
    return parsed.currency.confidence is Confidence.ASSUMED
