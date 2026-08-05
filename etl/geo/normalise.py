"""Tidy a location string enough to compare two of them.

Used by de-duplication: the same posting on two boards carries the same city
written two ways — "San Francisco, CA", "San Francisco, California, US",
"SF Bay Area". Normalising is not about being right, it is about being
consistent, so the transformations here are deliberately shallow and reversible
in meaning: nothing that changes which region a string resolves to.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalise_location", "location_tokens", "SEPARATORS"]

SEPARATORS = re.compile(r"[,;/|]+|\s+[-–—]\s+")
_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_WHITESPACE = re.compile(r"\s+")
_NOISE = re.compile(
    r"\b(remote|hybrid|on-?site|in[- ]office|flexible|optional|preferred|based|area|metro)\b",
    re.I,
)


def normalise_location(raw: str | None) -> str:
    """Casefold, strip accents and collapse whitespace. Keeps every place word.

    Accents go because "Zürich" and "Zurich" are the same city on two boards.
    Nothing is dropped here — the region tables are matched against this output,
    so removing a word could move a posting between buckets.
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKD", str(raw))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _WHITESPACE.sub(" ", text).strip().casefold()


def location_tokens(raw: str | None) -> tuple[str, ...]:
    """The place words in a location, in a stable order, with arrangement words removed.

    ``"San Francisco, CA (Hybrid)"`` and ``"Hybrid — CA, San Francisco"`` produce
    the same tuple, which is what lets de-duplication treat them as one place.
    The sort is what makes the order stable; it discards the city/country
    ordering, which is not information the boards agree on anyway.
    """
    text = normalise_location(raw)
    if not text:
        return ()
    text = _PARENTHETICAL.sub(r" \1 ", text)
    parts = (part.strip() for part in SEPARATORS.split(text))
    tokens = {_NOISE.sub("", part).strip() for part in parts}
    return tuple(sorted(token for token in tokens if token))
