"""The region buckets, and the place names that identify them.

Three buckets, not countries. A country-level breakdown would look more precise
and be less honest: most postings give a city, a state code, "Remote — EMEA", or
nothing, and inferring a country from that is guesswork dressed as data. Three
buckets are what the location strings actually support.

The tables below are word lists rather than a gazetteer on purpose. A real
geocoder would need a network call per posting, a key, and a cache — and would
still have to answer "Remote (EU)" out of a lookup table exactly like this one.
"""

from __future__ import annotations

import re
from enum import Enum

__all__ = ["Region", "REGIONS", "EU_PATTERN", "US_PATTERN", "US_DOTTED", "US_EXPLICIT", "COLLISION"]


class Region(str, Enum):
    """Where a posting is, at the granularity the data supports."""

    US = "us"
    EU = "eu"
    OTHER = "other"
    """Everywhere else, and everything unreadable. Deliberately one bucket: a
    fourth for "unknown" would split a sample that is already the smallest."""


REGIONS = tuple(r.value for r in Region)

# Europe: countries, capitals and the tech hubs that appear without a country,
# plus the shorthands boards use for a whole region.
EU_PATTERN = re.compile(
    r"\b(united kingdom|england|scotland|wales|ireland|london|germany|berlin|munich|"
    r"france|paris|spain|madrid|barcelona|netherlands|amsterdam|poland|warsaw|krakow|"
    r"sweden|stockholm|portugal|lisbon|porto|italy|rome|milan|belgium|brussels|austria|"
    r"vienna|denmark|copenhagen|finland|helsinki|norway|oslo|czech|prague|romania|"
    r"bucharest|estonia|tallinn|lithuania|latvia|greece|athens|hungary|budapest|"
    r"switzerland|zurich|zürich|luxembourg|bulgaria|croatia|slovakia|slovenia|"
    r"dublin|cork|belgrade|serbia|ukraine|kyiv|kiev|riga|vilnius|sofia|zagreb|"
    r"ljubljana|bratislava|malta|cyprus|iceland|"
    r"emea|europe|\beu\b|\buk\b)\b",
    re.I,
)

# "U.S." never matches inside \b(...)\b — the trailing dot is not a word
# character — so the dotted form needs its own pattern.
US_DOTTED = re.compile(r"u\.s\.a?\.?(?!\w)", re.I)

US_PATTERN = re.compile(
    r"\b(united states|\busa?\b|california|new york|nyc|new york city|texas|washington|"
    r"massachusetts|illinois|colorado|florida|san francisco|\bsf\b|sf bay|seattle|austin|"
    r"boston|chicago|los angeles|denver|atlanta|new jersey|virginia|oregon|arizona|"
    r"ca|ny|tx|wa|ma|il|ga|co|fl)\b",
    re.I,
)

#: Only these say "United States" beyond doubt. Used to break a collision.
US_EXPLICIT = re.compile(r"\b(united states|\busa\b)\b|u\.s\.a?\.?(?!\w)", re.I)

#: Places whose names collide with a US token and are not in the US: Georgia the
#: country against Georgia the state, London in Ontario, and ``CA`` meaning
#: Canada. Without this guard "Tbilisi, Georgia" is a US posting.
COLLISION = re.compile(
    r"\b(ontario|british columbia|toronto|vancouver|montreal|canada|"
    r"tbilisi|yerevan|armenia|baku|azerbaijan)\b",
    re.I,
)
