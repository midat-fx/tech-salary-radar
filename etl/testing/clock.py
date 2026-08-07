"""Hand-cranked time, for the code written against :mod:`etl.clock`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

__all__ = ["FixedClock", "RecordingSleeper", "DEFAULT_NOW"]

DEFAULT_NOW = datetime(2026, 8, 19, 9, 0, 0, tzinfo=timezone.utc)


@dataclass
class FixedClock:
    """A clock that only moves when the test moves it.

    ``today`` deliberately ignores the requested zone and derives the date from
    the same instant ``now`` reports. A fake that applied a real timezone would
    reintroduce the thing the port exists to remove: a test whose result depends
    on which side of midnight the machine is.
    """

    moment: datetime = DEFAULT_NOW

    def now(self) -> datetime:
        return self.moment

    def today(self, tz: str) -> date:  # noqa: ARG002 - zone deliberately ignored
        return self.moment.date()

    def advance(self, **delta) -> "FixedClock":
        """``advance(days=1)`` / ``advance(hours=3)``. Returns self, so it chains."""
        self.moment = self.moment + timedelta(**delta)
        return self

    def set(self, moment: datetime) -> "FixedClock":
        self.moment = moment
        return self


@dataclass
class RecordingSleeper:
    """Records the pauses instead of taking them.

    Every pause in this pipeline is an assertion waiting to be written — the
    crawl's politeness, the LLM's rate limit, the transport's backoff — and a
    recorded list is a stronger check than "the test eventually finished".
    """

    pauses: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        self.pauses.append(seconds)

    @property
    def total(self) -> float:
        return sum(self.pauses)

    @property
    def count(self) -> int:
        return len(self.pauses)
