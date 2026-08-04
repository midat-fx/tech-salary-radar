"""Pay periods, and the multipliers that turn one into an annual figure.

The multipliers are a modelling choice, not arithmetic. 2080 hours is 40 hours
across 52 weeks with no unpaid leave; a contractor working 46 paid weeks earns
less than this says. 260 days is the same assumption stated daily. They are
kept here, named, so the assumption is one edit away rather than three literals
in a parser.
"""

from __future__ import annotations

import re
from enum import Enum

from etl.config import HOURS_PER_YEAR, MONTHS_PER_YEAR, WEEKS_PER_YEAR

__all__ = ["Interval", "DAYS_PER_YEAR", "MULTIPLIER", "detect_interval", "to_annual"]

#: Working days in a year: 52 weeks of 5. Same assumption as HOURS_PER_YEAR.
DAYS_PER_YEAR = 260


class Interval(str, Enum):
    """The pay periods boards actually quote."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


MULTIPLIER: dict[Interval, int] = {
    Interval.HOUR: HOURS_PER_YEAR,
    Interval.DAY: DAYS_PER_YEAR,
    Interval.WEEK: WEEKS_PER_YEAR,
    Interval.MONTH: MONTHS_PER_YEAR,
    Interval.YEAR: 1,
}

# Ordered most specific first. "per year" must not be found inside "per year of
# experience", and an hourly rate must win over an annual word elsewhere in the
# same window — an hourly posting almost always also says "annually" somewhere.
_PATTERNS: tuple[tuple[Interval, re.Pattern[str]], ...] = (
    (Interval.HOUR, re.compile(r"per\s*hour|/\s*hour\b|\bhourly\b|\bp/?h\b|\ban hour\b|в час", re.I)),
    (Interval.DAY, re.compile(r"per\s*day|/\s*day\b|\bdaily rate\b|\bday rate\b|в день", re.I)),
    (Interval.WEEK, re.compile(r"per\s*week|/\s*week\b|\bweekly\b|в неделю", re.I)),
    (
        Interval.MONTH,
        re.compile(r"per\s*month|/\s*month\b|\bmonthly\b|pro monat|mensuel|в месяц", re.I),
    ),
    (
        Interval.YEAR,
        re.compile(r"per\s*(?:year|annum)|/\s*year\b|\bannual(?:ly)?\b|\bp\.?a\.?\b|в год", re.I),
    ),
)


def detect_interval(text: str | None, default: Interval = Interval.YEAR) -> Interval:
    """Read the pay period out of the wording around a figure.

    Defaults to yearly because that is what an unqualified range means on these
    boards. The cost of the default is real and asymmetric: a missed hourly rate
    is read as an annual salary of ``$75``, which the plausibility floor then
    throws away — a silent loss rather than a wrong number, which is the side to
    err on.
    """
    if not text:
        return default
    for interval, pattern in _PATTERNS:
        if pattern.search(text):
            return interval
    return default


def to_annual(amount: float | None, interval: Interval | str | None) -> float | None:
    """Scale an amount to a yearly figure. ``None`` passes through untouched.

    An unrecognised interval string is treated as yearly rather than refused:
    the boards send free text here, and the alternative is dropping a posting
    over a word.
    """
    if amount is None:
        return None
    return float(amount) * MULTIPLIER[_as_interval(interval)]


def _as_interval(value: Interval | str | None) -> Interval:
    if isinstance(value, Interval):
        return value
    text = (value or "year").lower()
    for interval in Interval:
        if interval.value in text:
            return interval
    return Interval.YEAR
