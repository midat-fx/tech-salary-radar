"""What has to be true before a day is written into an append-only history.

There is no later run that fixes an earlier day. A day written while a board was
down records a market collapse that never happened, and the timeseries carries
it forever. So the guards refuse rather than repair — see ADR 0005.
"""

from etl.guards.breaker import BreakerState, CircuitBreaker
from etl.guards.plausibility import (
    MAX_OTHER_REGION_SHARE,
    MAX_UNSPECIFIED_SHARE,
    MIN_SALARY_SHARE,
    check_plausibility,
    share,
)
from etl.guards.verdict import Finding, Severity, Verdict, refuse
from etl.guards.volume import (
    MIN_HISTORY_DAYS,
    SOURCE_FLOOR,
    TOTAL_FLOOR,
    WINDOW_DAYS,
    check_volume,
    source_medians,
)

__all__ = [
    "MAX_OTHER_REGION_SHARE",
    "MAX_UNSPECIFIED_SHARE",
    "MIN_HISTORY_DAYS",
    "MIN_SALARY_SHARE",
    "SOURCE_FLOOR",
    "TOTAL_FLOOR",
    "WINDOW_DAYS",
    "BreakerState",
    "CircuitBreaker",
    "Finding",
    "Severity",
    "Verdict",
    "check_plausibility",
    "check_volume",
    "refuse",
    "share",
    "source_medians",
]
