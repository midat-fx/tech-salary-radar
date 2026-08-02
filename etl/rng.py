"""The one door to randomness.

Two places in the pipeline are legitimately random, and they want opposite
things from that randomness.

The **crawl jitter** exists so 320 boards are not hit on a metronome; it wants
unpredictability in production and complete predictability in a test. The
**bootstrap resampler** wants a distribution, and it must produce the same
confidence interval every time the same day is aggregated — an interval that
moved between two runs over identical parquet would be indistinguishable from
the data having changed.

Both therefore go through a seeded generator, and no module outside this one
imports ``random``. A guard test enforces that (ADR 0007).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol, Sequence, TypeVar, runtime_checkable

__all__ = ["Rng", "SeededRng", "Jitter", "BOOTSTRAP_SEED", "JITTER_SEED", "bootstrap_rng"]

T = TypeVar("T")

# Fixed on the day the stratified bootstrap landed. Changing it moves every
# published confidence interval, so it is a versioned decision, not a constant
# to tweak: see ADR 0004.
BOOTSTRAP_SEED = 20260719

# The crawl's jitter seed. Unlike the bootstrap seed this one is arbitrary —
# what matters is only that a test can pin it.
JITTER_SEED = 20260718


@runtime_checkable
class Rng(Protocol):
    """The slice of :class:`random.Random` the pipeline actually uses."""

    def uniform(self, low: float, high: float) -> float:
        """A float in ``[low, high]``."""

    def choices(self, population: Sequence[T], k: int) -> list[T]:
        """``k`` draws with replacement — the bootstrap's resample."""


@dataclass
class SeededRng:
    """A :class:`random.Random` behind the narrow protocol above.

    Wrapping rather than exposing ``random.Random`` directly keeps the surface
    small enough that a fake is four lines, and stops a future caller reaching
    for ``shuffle`` or ``sample`` without a reason recorded here.
    """

    seed: int

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def uniform(self, low: float, high: float) -> float:
        return self._rng.uniform(low, high)

    def choices(self, population: Sequence[T], k: int) -> list[T]:
        return self._rng.choices(population, k=k)

    def reset(self) -> None:
        """Rewind to the seed. Two aggregations in one process must not differ."""
        self._rng = random.Random(self.seed)


def bootstrap_rng() -> SeededRng:
    """The generator every published confidence interval is drawn from."""
    return SeededRng(BOOTSTRAP_SEED)


@dataclass
class Jitter:
    """Politeness spread for the crawl: ``base`` plus a small random offset.

    The offset is bounded and additive rather than multiplicative because the
    point is to break up a regular pattern, not to slow the crawl down: 320
    boards at half a second are already three minutes of walking.
    """

    base_seconds: float
    spread_low: float = 0.2
    spread_high: float = 0.4
    rng: Rng | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = SeededRng(JITTER_SEED)
        if self.spread_low > self.spread_high:
            raise ValueError("jitter spread_low must not exceed spread_high")

    def next_pause(self) -> float:
        """The next pause in seconds. Never negative, whatever the base is."""
        assert self.rng is not None  # set in __post_init__
        return max(0.0, self.base_seconds + self.rng.uniform(self.spread_low, self.spread_high))
