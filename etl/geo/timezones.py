"""Which working hours a posting expects, and why that is a pay question.

"Remote" on its own is not a market. A remote role that requires overlap with
Pacific time is competing for American engineers and pays like one; a remote
role anchored to CET is competing in Europe. The two land in the same
``is_remote`` bucket and in very different parts of the salary distribution, and
the only evidence available is what the location string says about hours.

This is deliberately coarse. Boards do not send a timezone field, so what is
here is the wording employers actually use — an explicit zone name, a UTC
offset, or a region shorthand — and nothing is inferred from a city. Inferring
would need a city-to-zone table that would immediately disagree with the region
tables next door.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = ["Anchor", "TimezoneHint", "detect_timezone", "OVERLAP_PATTERNS"]


class Anchor(str, Enum):
    """The working-hours market a remote posting is anchored to."""

    AMERICAS = "americas"
    EUROPE = "europe"
    ASIA_PACIFIC = "apac"
    ANYWHERE = "anywhere"
    """Explicitly no overlap requirement — genuinely global, and rare."""

    UNSTATED = "unstated"
    """Nothing said. The common case, and not the same as ``anywhere``."""


#: Ordered: an explicit zone beats a region shorthand, which beats an offset.
OVERLAP_PATTERNS: tuple[tuple[Anchor, re.Pattern[str]], ...] = (
    (
        Anchor.AMERICAS,
        re.compile(
            r"\b(pacific time|\bpt\b|\bpst\b|\bpdt\b|eastern time|\bet\b|\best\b|\bedt\b|"
            r"central time|\bcst\b|\bmst\b|us hours|us time ?zones?|americas)\b",
            re.I,
        ),
    ),
    (
        Anchor.EUROPE,
        # "gmt" only counts as a named zone when no offset follows it:
        # "GMT overlap" is European hours, "GMT+8" is an offset that is not.
        re.compile(
            r"\b(cet|cest|\bbst\b|gmt(?!\s*[+\-±]\s*\d)|wet|eet|"
            r"european time ?zones?|uk hours|central european)\b",
            re.I,
        ),
    ),
    (
        Anchor.ASIA_PACIFIC,
        re.compile(r"\b(jst|ist|sgt|aest|aedt|apac hours|asia[- ]pacific time)\b", re.I),
    ),
    (
        Anchor.ANYWHERE,
        re.compile(r"\b(any time ?zone|anywhere in the world|fully async|no overlap)\b", re.I),
    ),
)

#: "UTC+2", "GMT-5", "UTC±3". Read as an offset, mapped to the nearest market.
_OFFSET = re.compile(r"\b(?:utc|gmt)\s*([+\-±])\s*(\d{1,2})", re.I)


@dataclass(frozen=True)
class TimezoneHint:
    """What the location string said about hours, and how firmly."""

    anchor: Anchor
    offset_hours: int | None = None
    source: str = "none"

    @property
    def is_anchored(self) -> bool:
        """True when the posting names a market rather than saying nothing."""
        return self.anchor not in (Anchor.UNSTATED, Anchor.ANYWHERE)


def _from_offset(offset: int) -> Anchor:
    """Map a UTC offset onto the three markets.

    The boundaries are where the working day stops overlapping: an offset west
    of UTC-2 cannot share a morning with Europe, and one east of UTC+5 cannot
    share an afternoon with it.
    """
    if offset <= -2:
        return Anchor.AMERICAS
    if offset >= 6:
        return Anchor.ASIA_PACIFIC
    return Anchor.EUROPE


def detect_timezone(text: str | None) -> TimezoneHint:
    """Read an hours anchor out of a location string or a job title."""
    if not text:
        return TimezoneHint(Anchor.UNSTATED)
    for anchor, pattern in OVERLAP_PATTERNS:
        if pattern.search(text):
            return TimezoneHint(anchor, source="named")
    match = _OFFSET.search(text)
    if match:
        sign, digits = match.groups()
        offset = int(digits) * (-1 if sign == "-" else 1)
        return TimezoneHint(_from_offset(offset), offset_hours=offset, source="offset")
    return TimezoneHint(Anchor.UNSTATED)
