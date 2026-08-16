"""Where a posting is: the region bucket, the remote reading, and the tidying
that lets two boards' spellings of one city be compared.

Region is three buckets rather than countries because that is what the location
strings support — see :mod:`etl.geo.regions`.
"""

from etl.geo.detect import Certainty, RegionGuess, detect_region, region_of
from etl.geo.normalise import SEPARATORS, location_tokens, normalise_location
from etl.geo.regions import COLLISION, EU_PATTERN, REGIONS, US_PATTERN, Region
from etl.geo.timezones import Anchor, TimezoneHint, detect_timezone
from etl.geo.remote import HYBRID, REMOTE_WORDS, RemoteReading, is_remote_text, read_remote

__all__ = [
    "COLLISION",
    "EU_PATTERN",
    "HYBRID",
    "REGIONS",
    "REMOTE_WORDS",
    "SEPARATORS",
    "Anchor",
    "Certainty",
    "Region",
    "RegionGuess",
    "RemoteReading",
    "US_PATTERN",
    "TimezoneHint",
    "detect_region",
    "detect_timezone",
    "is_remote_text",
    "location_tokens",
    "normalise_location",
    "read_remote",
    "region_of",
]
