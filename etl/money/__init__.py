"""Pay: what a board said, what it means annually in USD, and whether to believe it.

The pipeline's most consequential contract. Everything the site publishes is a
median of the midpoints this package produces, so a rule that is wrong here is
wrong in every figure downstream — and wrong quietly, because a salary is a
plausible number whatever it actually was.

The stages, in order:

1. :mod:`etl.money.parse` finds a range in text, anchored to salary wording.
2. :mod:`etl.money.currency` decides what unit it is in, and how sure that is.
3. :mod:`etl.money.interval` decides what period it covers.
4. :mod:`etl.money.policy` decides whether to believe it, and says why not.
5. :mod:`etl.money.convert` annualises, converts, and judges the result again.

See ADR 0001 (annual gross USD) and ADR 0002 (midpoint, not mean).
"""

from etl.money.convert import (
    NO_PAY,
    ConversionResult,
    convert_range,
    is_weak_currency_guess,
    to_usd,
)
from etl.money.currency import (
    AMBIGUOUS_SYMBOLS,
    SUPPORTED,
    SYMBOL_TO_CURRENCY,
    Confidence,
    CurrencyGuess,
    from_code,
    from_symbol,
    normalise_code,
)
from etl.money.interval import DAYS_PER_YEAR, MULTIPLIER, Interval, detect_interval, to_annual
from etl.money.parse import (
    ANCHOR_WINDOW,
    currency_from_text,
    find_anchored_range,
    find_range,
    parse_amount,
)
from etl.money.policy import (
    MAX_SPREAD,
    PRE_CONVERSION_FLOOR,
    Judgement,
    Verdict,
    confidence_penalty,
    judge_annual_usd,
    judge_parsed,
)
from etl.money.range import PayRange, midpoint

__all__ = [
    "AMBIGUOUS_SYMBOLS",
    "ANCHOR_WINDOW",
    "DAYS_PER_YEAR",
    "MAX_SPREAD",
    "MULTIPLIER",
    "NO_PAY",
    "PRE_CONVERSION_FLOOR",
    "SUPPORTED",
    "SYMBOL_TO_CURRENCY",
    "Confidence",
    "ConversionResult",
    "CurrencyGuess",
    "Interval",
    "Judgement",
    "PayRange",
    "Verdict",
    "confidence_penalty",
    "convert_range",
    "currency_from_text",
    "detect_interval",
    "find_anchored_range",
    "find_range",
    "from_code",
    "from_symbol",
    "is_weak_currency_guess",
    "judge_annual_usd",
    "judge_parsed",
    "midpoint",
    "normalise_code",
    "parse_amount",
    "to_annual",
    "to_usd",
]
