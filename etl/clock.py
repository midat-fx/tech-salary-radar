"""The one door to wall-clock time.

Every module under ``etl/`` that needs to know what time it is takes a
:class:`Clock` and asks it. Nothing else in the package calls ``datetime.now``,
``date.today`` or ``time.time`` — a guard test enforces that (see
``tests/test_determinism_guard.py``) and ADR 0007 explains why.

The reason is not purity. The pipeline decides a snapshot's partition date, how
stale the FX cache is and how old a label is; all three used to read the machine
clock at the point of use, so a test that touched them either asserted nothing
or asserted something that would break at midnight, in another timezone, or on
a slow runner. With the clock injected, those are ordinary pure functions of a
value the test supplies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

__all__ = [
    "Clock",
    "SystemClock",
    "Sleeper",
    "SystemSleeper",
    "age_in_days",
    "iso_day",
    "iso_second",
    "parse_iso",
]


@runtime_checkable
class Clock(Protocol):
    """A source of the current instant, always timezone-aware and in UTC."""

    def now(self) -> datetime:
        """Current instant as an aware UTC datetime."""

    def today(self, tz: str) -> date:
        """Calendar date in ``tz`` — the partition a run belongs to."""


@dataclass(frozen=True)
class SystemClock:
    """The machine clock. The only reader of ambient time in the package."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self, tz: str) -> date:
        return datetime.now(ZoneInfo(tz)).date()


@runtime_checkable
class Sleeper(Protocol):
    """A pause. Injected so politeness towards a third-party API costs a test nothing."""

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``."""


@dataclass
class SystemSleeper:
    """Real pauses, and a record of what was slept for.

    The record exists because the crawl's pacing is a property worth asserting
    in production too: the run report prints how much of a run was spent
    waiting, which is the difference between "the boards are slow" and "we are
    being polite".
    """

    total_seconds: float = field(default=0.0)

    def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self.total_seconds += seconds
        time.sleep(seconds)


def iso_day(moment: datetime) -> str:
    """``2026-08-19`` — the form used for parquet partitions and snapshot dates."""
    return moment.date().isoformat()


def iso_second(moment: datetime) -> str:
    """``2026-08-19T07:48:11Z`` — second precision, ``Z`` suffix, no microseconds.

    Written into every published JSON. Microseconds would make two runs over
    identical data produce different bytes for no reader's benefit.
    """
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(raw: str | None) -> datetime | None:
    """Parse an ISO-8601 string, accepting the ``Z`` suffix; ``None`` when unparseable.

    Board APIs are inconsistent about the suffix and occasionally send an empty
    string, so this never raises: a timestamp that cannot be read is absent, not
    fatal.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_in_days(stamp: str | date | datetime | None, now: datetime) -> int | None:
    """Whole days between ``stamp`` and ``now``; ``None`` when ``stamp`` is unreadable.

    Negative for a stamp in the future — a board that reports tomorrow's date is
    a data problem the caller should see, not something to clamp to zero here.
    """
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        moment = stamp
    elif isinstance(stamp, date):
        moment = datetime.combine(stamp, datetime.min.time(), tzinfo=timezone.utc)
    else:
        moment = parse_iso(stamp)
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc).date() - moment.astimezone(timezone.utc).date()).days


def plus_days(moment: datetime, days: int) -> datetime:
    """``moment`` shifted by whole days, keeping the timezone."""
    return moment + timedelta(days=days)
