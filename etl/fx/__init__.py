"""Currency rates: where they come from, how old they are, and how they apply.

Only USD, GBP and EUR are ever converted (ADR 0001). The cascade exists because
neither public source is under anyone's control here, and the cache is a third
source rather than an optimisation.
"""

from etl.fx.cascade import (
    ER_API,
    JSDELIVR,
    SOURCES,
    FxError,
    cache_path,
    fetch_rates,
    read_cache,
)
from etl.fx.convert import convert_pair, to_usd
from etl.fx.rates import MAX_AGE_DAYS, RateTable

__all__ = [
    "ER_API",
    "JSDELIVR",
    "MAX_AGE_DAYS",
    "SOURCES",
    "FxError",
    "RateTable",
    "cache_path",
    "convert_pair",
    "fetch_rates",
    "read_cache",
    "to_usd",
]
