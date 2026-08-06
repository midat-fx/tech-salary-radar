"""The three ATS adapters, the transport they share, and the seed that drives them.

Each adapter is a pure ``parse(payload, slug)`` plus a thin ``fetch`` that adds
the HTTP call, so a board's response shape can be tested against a recorded
sample with no network anywhere near it.
"""

from etl.sources import ashby, greenhouse, lever
from etl.sources.html import collapse_whitespace, strip_html
from etl.sources.seed import SeedEntry, SeedReport, load_seed, read_seed, validate_seed
from etl.sources.transport import MAX_ATTEMPTS, Transient, build_client, get_json

#: source name -> fetcher. The crawl looks a board's ATS up here; a name that is
#: absent contributes nothing rather than raising, because the seed is older
#: than the code and may mention an ATS that was never implemented.
FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}

#: source name -> pure parser, for tests and for replaying a recorded payload.
PARSERS = {
    "greenhouse": greenhouse.parse,
    "lever": lever.parse,
    "ashby": ashby.parse,
}

__all__ = [
    "FETCHERS",
    "MAX_ATTEMPTS",
    "PARSERS",
    "SeedEntry",
    "SeedReport",
    "Transient",
    "ashby",
    "build_client",
    "collapse_whitespace",
    "get_json",
    "greenhouse",
    "lever",
    "load_seed",
    "read_seed",
    "strip_html",
    "validate_seed",
]
