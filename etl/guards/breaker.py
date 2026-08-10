"""Stop hammering an ATS that is down, without stopping the crawl.

Boards fail one at a time and they fail all at once, and the two want opposite
responses. A single dead board is normal — the seed is months old — and costs
one request. A whole ATS returning 429 costs one request *per board*, and with
two hundred Greenhouse boards in the seed that is two hundred requests into a
service that is already asking us to stop, plus the retry ladder behind each.

The breaker counts consecutive failures per source and stops asking that source
once they pile up. Consecutive, not total: a source that fails a board here and
there is working, and resetting on every success is what tells the two cases
apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etl.config import FETCH_CIRCUIT_BREAK

__all__ = ["CircuitBreaker", "BreakerState"]


@dataclass
class BreakerState:
    """Per-source counters, kept for the run report."""

    consecutive: int = 0
    failures: int = 0
    successes: int = 0
    tripped: bool = False


@dataclass
class CircuitBreaker:
    """One breaker per crawl, holding a state per source."""

    threshold: int = FETCH_CIRCUIT_BREAK
    states: dict[str, BreakerState] = field(default_factory=dict)

    def state(self, source: str) -> BreakerState:
        return self.states.setdefault(source, BreakerState())

    def is_open(self, source: str) -> bool:
        """True when this source should be skipped for the rest of the run."""
        return self.state(source).tripped

    def record_success(self, source: str) -> None:
        state = self.state(source)
        state.consecutive = 0
        state.successes += 1

    def record_failure(self, source: str) -> bool:
        """Count a failure. Returns True when this one tripped the breaker."""
        state = self.state(source)
        state.consecutive += 1
        state.failures += 1
        if not state.tripped and state.consecutive >= self.threshold:
            state.tripped = True
            return True
        return False

    @property
    def tripped_sources(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, st in self.states.items() if st.tripped))

    def describe(self) -> str:
        if not self.states:
            return "breaker: no boards attempted"
        parts = [
            f"{source}: {st.successes} ok / {st.failures} failed"
            + (" (tripped)" if st.tripped else "")
            for source, st in sorted(self.states.items())
        ]
        return "breaker: " + ", ".join(parts)
