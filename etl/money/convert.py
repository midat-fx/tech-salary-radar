"""Turn a posted range into the one annual gross USD figure everything is built on.

The order matters and is not obvious: annualise **first**, then convert. A
monthly EUR 5,000–6,000 band is a normal European salary; judged before
annualising it looks like a rounding error, and judged after converting but
before annualising it looks like one too. Doing it in this order is what lets
the plausibility floor be a single number instead of one per currency.
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.money.currency import Confidence
from etl.money.policy import Judgement, Verdict, judge_annual_usd, judge_parsed
from etl.money.range import PayRange, midpoint

__all__ = ["ConversionResult", "to_usd", "convert_range", "NO_PAY"]


def to_usd(amount: float | None, currency: str | None, rates: dict[str, float]) -> float | None:
    """``amount`` in ``currency`` -> USD, using units-per-USD rates.

    Returns ``None`` when the currency has no rate. That is deliberately not an
    error and deliberately not a pass-through: treating an unconvertible figure
    as USD is how a 12,000,000 JPY salary becomes a twelve-million-dollar one.
    """
    if amount is None:
        return None
    code = (currency or "USD").upper()
    if code == "USD":
        return float(amount)
    rate = rates.get(code)
    if not rate:
        return None
    return float(amount) / rate


@dataclass(frozen=True)
class ConversionResult:
    """The stored form of a posting's pay, plus why it looks the way it does."""

    low_usd: float | None
    high_usd: float | None
    mid_usd: float | None
    has_salary: bool
    judgement: Judgement
    #: What the board actually quoted, kept so a published figure can be traced
    #: back to its source without re-running the crawl.
    currency_original: str | None = None
    low_original: float | None = None
    high_original: float | None = None
    interval_original: str | None = None

    @property
    def dropped(self) -> bool:
        """True when a range was found and then refused — distinct from none found."""
        return not self.has_salary and self.judgement.verdict not in (Verdict.EMPTY,)

    def to_row(self) -> dict[str, object]:
        """The columns the snapshot and job tables expect."""
        return {
            "salary_min_usd": self.low_usd,
            "salary_max_usd": self.high_usd,
            "salary_mid_usd": self.mid_usd,
            "has_salary": self.has_salary,
            "dropped_oob": self.dropped,
            "currency_original": self.currency_original,
            "salary_min_orig": self.low_original,
            "salary_max_orig": self.high_original,
            "salary_interval_orig": self.interval_original,
        }


#: A posting with nothing to say about pay. Not a failure — most postings.
NO_PAY = ConversionResult(None, None, None, False, Judgement(Verdict.EMPTY))


def convert_range(parsed: PayRange | None, rates: dict[str, float]) -> ConversionResult:
    """Judge, annualise, convert, judge again. Returns the storable result either way."""
    verdict = judge_parsed(parsed)
    if parsed is None or parsed.is_empty:
        return NO_PAY
    original = {
        "currency_original": parsed.currency.code,
        "low_original": parsed.low,
        "high_original": parsed.high,
        "interval_original": parsed.interval.value,
    }
    if not verdict.accepted:
        return ConversionResult(None, None, None, False, verdict, **original)

    annual = parsed.annualised()
    low = to_usd(annual.low, annual.currency.code, rates)
    high = to_usd(annual.high, annual.currency.code, rates)
    if annual.low is not None and low is None or annual.high is not None and high is None:
        # A supported currency with no rate today: the FX cascade fell through to
        # a stale cache that predates it. Excluded, not approximated.
        return ConversionResult(
            None,
            None,
            None,
            False,
            Judgement(Verdict.UNSUPPORTED_CURRENCY, f"no rate for {annual.currency.code}"),
            **original,
        )

    mid = midpoint(low, high)
    final = judge_annual_usd(mid, low, high)
    if not final.accepted:
        return ConversionResult(None, None, None, False, final, **original)
    return ConversionResult(low, high, mid, True, final, **original)


def is_weak_currency_guess(parsed: PayRange | None) -> bool:
    """Whether the currency behind a figure was assumed rather than stated."""
    return parsed is not None and parsed.currency.confidence is Confidence.ASSUMED
