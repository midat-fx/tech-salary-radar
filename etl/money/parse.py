"""Find a pay range in free text.

Greenhouse has no compensation field at all: US pay-transparency law put the
range into the job description, so the only way to it is reading the ad. That
makes this the most failure-prone module in the pipeline — a job description
is full of numbers that are not pay, and every one of them is a plausible
salary if you squint.

The defences, in the order they apply:

* **Anchoring.** A range must sit near salary wording. Without that, the first
  two dollar figures in the ad win, and those are usually a 401k match or the
  company's funding round.
* **Code before symbol.** ``GBP 90,000 - 110,000`` carries no symbol and would
  otherwise be swallowed by the generic pattern and labelled USD.
* **Suffix propagation.** ``$150-200K`` means both bounds in thousands.
* **European decimals.** ``€70.000`` is seventy thousand, not seventy.
"""

from __future__ import annotations

import re
from typing import Callable

from etl.money.currency import Confidence, CurrencyGuess, from_code, from_symbol
from etl.money.interval import detect_interval
from etl.money.range import PayRange

__all__ = ["ANCHOR_WINDOW", "find_range", "find_anchored_range", "parse_amount"]

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)"
_SEP = r"\s*(?:-|–|—|to|до)\s*"

# "$150,000 - $180,000", "£85,000 – £100,000", "$150-200K", "€70.000 - €90.000"
_PAIR = re.compile(rf"([$£€])?\s?{_NUM}\s*([KkMm])?{_SEP}(?:[$£€])?\s?{_NUM}\s*([KkMm])?")
# "GBP 90,000 - 110,000" — an ISO code instead of a symbol.
_PAIR_CODE = re.compile(rf"\b(USD|GBP|EUR)\b\s*{_NUM}\s*([KkMm])?{_SEP}{_NUM}\s*([KkMm])?", re.I)
# "starting at $180,000", "from £95,000" — a floor with no ceiling.
_ONE_SIDED = re.compile(
    rf"\b(?:from|starting at|starts at|at least|minimum of|от)\b\W{{0,12}}([$£€])?\s?{_NUM}\s*([KkMm])?",
    re.I,
)

_ANCHOR = re.compile(
    r"(salary|base pay|base salary|pay range|compensation|annual|remuneration|"
    r"pay band|salary range|hourly rate|rate of pay)",
    re.I,
)

#: Characters either side of the anchor word to search for a figure. Wide enough
#: for "The base salary range for this position is $150,000 - $180,000", narrow
#: enough that the next paragraph's numbers stay out.
ANCHOR_WINDOW = 150

_EU_THOUSANDS = re.compile(r"\d{1,3}\.\d{3}")


def parse_amount(raw: str, suffix: str | None = None) -> float:
    """``'150,000'`` / ``'70.000'`` / ``'211.4'`` + ``'K'`` -> a float.

    The European thousands dot is only read as a separator when the shape is
    exactly three trailing digits and no magnitude suffix follows. ``211.4K``
    has to stay 211.4 thousand, and ``1.500`` in an English ad is ambiguous —
    the three-digit rule resolves it towards the reading that is far more common
    in these postings.
    """
    text = raw.strip()
    magnitude = (suffix or "").lower()
    if _EU_THOUSANDS.fullmatch(text) and not magnitude:
        value = float(text.replace(".", ""))
    else:
        value = float(text.replace(",", ""))
    if magnitude == "k":
        value *= 1_000
    elif magnitude == "m":
        value *= 1_000_000
    return value


def _pair_from_match(match: re.Match[str], code_form: bool) -> tuple[float, float, CurrencyGuess]:
    if code_form:
        code, low_raw, low_suffix, high_raw, high_suffix = (
            match.group(1).upper(),
            *match.groups()[1:],
        )
        currency = from_code(code, declared=False)
    else:
        symbol, low_raw, low_suffix, high_raw, high_suffix = match.groups()
        currency = from_symbol(symbol)
    if high_suffix and not low_suffix:
        # "$150-200K": the magnitude is stated once and governs both bounds.
        low_suffix = high_suffix
    return parse_amount(low_raw, low_suffix), parse_amount(high_raw, high_suffix), currency


def _ranges_in(text: str, origin: str) -> list[tuple[int, PayRange]]:
    """Every range the patterns find, with where it starts, in document order.

    Code-form matches are collected exclusively when any exist: the generic
    pattern also matches inside ``GBP 90,000 - 110,000`` and would label it USD.
    """
    found: list[tuple[int, PayRange]] = []
    coded = list(_PAIR_CODE.finditer(text))
    for match in coded or list(_PAIR.finditer(text)):
        low, high, currency = _pair_from_match(match, code_form=bool(coded))
        found.append((match.start(), PayRange(low, high, currency, detect_interval(text), origin)))
    if found:
        return found
    for match in _ONE_SIDED.finditer(text):
        symbol, low_raw, suffix = match.groups()
        found.append(
            (
                match.start(),
                PayRange(
                    parse_amount(low_raw, suffix),
                    None,
                    from_symbol(symbol),
                    detect_interval(text),
                    f"{origin}:one-sided",
                ),
            )
        )
    return found


def find_range(text: str | None, origin: str = "text") -> PayRange | None:
    """First pay range in ``text``, without anchoring. ``None`` when there is none.

    Used on fields a board dedicates to compensation, where every number present
    is already about pay — an Ashby summary string, a Lever range. For a job
    description use :func:`find_anchored_range` instead.
    """
    if not text:
        return None
    found = _ranges_in(text, origin)
    return found[0][1] if found else None


def find_anchored_range(
    text: str | None,
    window: int = ANCHOR_WINDOW,
    accept: Callable[[PayRange], bool] | None = None,
) -> PayRange | None:
    """Search only near salary wording, forwards from the anchor before backwards.

    Direction is the whole defence. Pay-transparency wording puts the figure
    *after* the phrase — "The base salary range for this position is $150,000 -
    $180,000" — so the text following an anchor is where pay lives. Text
    preceding it is mostly other things: a signing bonus, a 401k match, the
    funding round. Searching a symmetric window around the anchor picks those up
    and reports a bonus as a salary.

    The backward pass exists because "$150,000 - $180,000 base salary" does
    occur; it takes the match *closest* to the anchor rather than the first one
    in the window, for the same reason.

    ``accept`` is consulted for every candidate, and a rejection does **not** end
    the search — it moves on to the next one. An ad that quotes an uncapped OTE
    band under "Annual compensation" and its real base salary two sentences
    later is the case this exists for: taking the first anchored match and
    stopping would publish the OTE.
    """
    if not text:
        return None
    anchors = list(_ANCHOR.finditer(text))
    for origin, snippets in (
        ("description", [text[a.end() : a.end() + window] for a in anchors]),
        ("description:before", [text[max(0, a.start() - window) : a.start()] for a in anchors]),
    ):
        backwards = origin.endswith(":before")
        for snippet in snippets:
            candidates = [candidate for _, candidate in _ranges_in(snippet, origin)]
            if backwards:
                candidates.reverse()   # closest to the anchor first
            for candidate in candidates:
                if accept is None or accept(candidate):
                    return candidate
    return None


def currency_from_text(text: str | None) -> CurrencyGuess:
    """Best guess at the currency of a figure in ``text``, for callers with no range."""
    if text:
        code = re.search(r"\b(USD|GBP|EUR)\b", text, re.I)
        if code:
            return from_code(code.group(1), declared=False)
        symbol = re.search(r"[£€$]", text)
        if symbol:
            return from_symbol(symbol.group(0))
    return CurrencyGuess("USD", Confidence.ASSUMED)
