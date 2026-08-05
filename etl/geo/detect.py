"""Read a region out of a location string, and say how confident that is.

The order of the checks is the whole content of this module, and it is not
alphabetical: it is the order in which the failure modes were found.

1. **Collision first.** "London, Ontario" matches Europe on *london*, and
   "Tbilisi, Georgia" matches the US on *georgia*. A name that collides is
   resolved to neither unless something says otherwise.
2. **Europe before the US.** The US pattern includes two-letter state codes, and
   ``CA``/``CO``/``IL`` collide with far too much. Europe's tokens are longer and
   therefore safer, so a string matching both is European.
3. **Dotted US last.** ``U.S.`` needs a pattern of its own because the trailing
   dot is not a word character.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from etl.geo.regions import COLLISION, EU_PATTERN, US_DOTTED, US_EXPLICIT, US_PATTERN, Region

__all__ = ["Certainty", "RegionGuess", "detect_region", "region_of"]


class Certainty(str, Enum):
    """How the region was reached. Carried so the run report can watch the mix."""

    NAMED = "named"
    """A country or an unambiguous city was present."""

    COLLIDED = "collided"
    """A token matched both a US place and a non-US one, and nothing broke the
    tie. Resolved to ``other`` rather than guessed."""

    ABSENT = "absent"
    """Nothing recognisable. Also ``other`` — but for a different reason, and a
    run where this share jumps means a board stopped sending locations."""


@dataclass(frozen=True)
class RegionGuess:
    region: Region
    certainty: Certainty

    @property
    def value(self) -> str:
        return self.region.value


def detect_region(location_raw: str | None, country: str | None = None) -> RegionGuess:
    """Region and certainty for a location string, plus an optional country field."""
    text = f"{location_raw or ''} {country or ''}".strip()
    if not text:
        return RegionGuess(Region.OTHER, Certainty.ABSENT)

    if COLLISION.search(text) and not US_EXPLICIT.search(text):
        # "London, Ontario" would otherwise be European, "Tbilisi, Georgia" US.
        return RegionGuess(Region.OTHER, Certainty.COLLIDED)
    if EU_PATTERN.search(text):
        return RegionGuess(Region.EU, Certainty.NAMED)
    if US_DOTTED.search(text) or US_PATTERN.search(text):
        return RegionGuess(Region.US, Certainty.NAMED)
    return RegionGuess(Region.OTHER, Certainty.ABSENT)


def region_of(location_raw: str | None, country: str | None = None) -> str:
    """The stored bucket: ``us``, ``eu`` or ``other``."""
    return detect_region(location_raw, country).value
