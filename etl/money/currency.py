"""Which currency a posted figure is in, and how confident we are about it.

Boards state currency three ways and sometimes not at all: a structured code
(`"currencyCode": "GBP"`), a symbol in free text (`£85,000`), or an ISO code in
free text (`GBP 90,000`). The three are not equally reliable and the difference
matters — `$` alone is ambiguous across at least a dozen dollars, and reading a
Canadian or Australian range as USD moves it by a quarter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Confidence",
    "CurrencyGuess",
    "SUPPORTED",
    "SYMBOL_TO_CURRENCY",
    "AMBIGUOUS_SYMBOLS",
    "from_symbol",
    "from_code",
    "normalise_code",
]


class Confidence(str, Enum):
    """How the currency was learned. Lower confidence is not lower value —
    it is a fact the plausibility rules are allowed to weigh."""

    DECLARED = "declared"
    """The board sent a currency code in a structured field. Trust it."""

    CODE_IN_TEXT = "code-in-text"
    """An ISO code appeared next to the figure: ``GBP 90,000 - 110,000``."""

    SYMBOL = "symbol"
    """Only a symbol was present. Unambiguous for £ and €."""

    ASSUMED = "assumed"
    """Nothing said. The figure is read as USD because the boards are
    US-centric — and that assumption is exactly what ADR 0001 records as a bias
    rather than hides as a default."""


#: The currencies the pipeline converts. Everything else is left unconverted and
#: therefore excluded from the salary statistics: an unconvertible figure is
#: worse than a missing one, because it looks like a number.
SUPPORTED = ("USD", "GBP", "EUR")

#: Symbols that identify exactly one supported currency.
SYMBOL_TO_CURRENCY = {"£": "GBP", "€": "EUR"}

#: ``$`` is used by USD, CAD, AUD, NZD, SGD, HKD and more. On a US-centric board
#: set it means USD far more often than not, so it resolves to USD — but at
#: :attr:`Confidence.ASSUMED`, so the decision is visible rather than baked in.
AMBIGUOUS_SYMBOLS = {"$"}


@dataclass(frozen=True)
class CurrencyGuess:
    """A currency and how it was learned."""

    code: str
    confidence: Confidence

    @property
    def is_supported(self) -> bool:
        return self.code in SUPPORTED

    @property
    def is_certain(self) -> bool:
        return self.confidence in (Confidence.DECLARED, Confidence.CODE_IN_TEXT)


def normalise_code(raw: str | None) -> str | None:
    """Upper-case a currency code, or ``None`` if there is nothing to read."""
    if raw is None:
        return None
    code = str(raw).strip().upper()
    return code or None


def from_code(raw: str | None, declared: bool = True) -> CurrencyGuess:
    """A currency the board named. Falls back to an assumed USD when it named none."""
    code = normalise_code(raw)
    if code is None:
        return CurrencyGuess("USD", Confidence.ASSUMED)
    return CurrencyGuess(code, Confidence.DECLARED if declared else Confidence.CODE_IN_TEXT)


def from_symbol(symbol: str | None) -> CurrencyGuess:
    """A currency read from a symbol in free text."""
    if not symbol:
        return CurrencyGuess("USD", Confidence.ASSUMED)
    if symbol in SYMBOL_TO_CURRENCY:
        return CurrencyGuess(SYMBOL_TO_CURRENCY[symbol], Confidence.SYMBOL)
    if symbol in AMBIGUOUS_SYMBOLS:
        return CurrencyGuess("USD", Confidence.ASSUMED)
    return CurrencyGuess("USD", Confidence.ASSUMED)
