"""Everything a run needs, assembled once at the edge.

The pipeline stages take this rather than reaching for defaults. Two reasons,
and only the second is about testing: the ports have to be threaded through
anyway (ADR 0007), and a run that builds its own clock halfway down cannot be
made to disagree with the one that started it — which is exactly the bug that
made a snapshot land in the wrong partition when a run crossed midnight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from etl.clock import Clock, Sleeper, SystemClock, SystemSleeper
from etl.config import TZ

__all__ = ["RunContext", "build_context"]


@dataclass
class RunContext:
    """One run's identity, destinations and ports."""

    day: str
    data_dir: Path
    site_data_dir: Path
    clock: Clock
    sleeper: Sleeper
    log: object = print
    skip_llm: bool = True
    llm_limit: int | None = None
    pause: float | None = None
    _messages: list[str] = field(default_factory=list)

    def say(self, message: str) -> None:
        """Log, and keep a copy so a test can assert on what a run reported."""
        self._messages.append(message)
        self.log(message)

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(self._messages)

    def partition(self, table: str) -> Path:
        return self.data_dir / table / f"dt={self.day}"


def build_context(
    data_dir="data",
    site_data_dir="site/data",
    day: str | None = None,
    clock: Clock | None = None,
    sleeper: Sleeper | None = None,
    **options,
) -> RunContext:
    """Assemble a context, deriving the day from the clock when it is not given.

    The day comes from the reporting timezone rather than UTC: a run that starts
    at 02:00 Almaty belongs to that Almaty day, and the partition name is what
    the dashboard's date axis shows.
    """
    clock = clock or SystemClock()
    return RunContext(
        day=day or clock.today(TZ).isoformat(),
        data_dir=Path(data_dir),
        site_data_dir=Path(site_data_dir),
        clock=clock,
        sleeper=sleeper or SystemSleeper(),
        **options,
    )
