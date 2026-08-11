"""Confidence intervals for a ratio of medians, by stratified resampling.

A skill premium is a weighted mean of per-stratum median ratios. There is no
closed form for its sampling distribution, and the strata are small — eight
postings is the minimum a stratum needs to take part — so the interval has to
be estimated by resampling.

Stratified, not pooled: resampling across strata would let a bootstrap draw
change the *composition* of the sample, and the premium is defined as a
comparison within a level and region. Drawing within each stratum keeps the
comparison the same one in every replicate.

The generator is seeded (:mod:`etl.rng`). An interval that moved between two
aggregations of the same parquet would be indistinguishable from the data
having changed, which is the one thing a published interval must not be.
"""

from __future__ import annotations

from statistics import median

__all__ = ["REPLICATES", "MIN_STRATUM", "weighted_premium", "bootstrap_interval"]

#: Enough that the 2.5/97.5 percentiles are stable to a decimal place.
REPLICATES = 1000

#: A stratum needs this many postings on each side to contribute. Below it the
#: median is one or two people's salaries.
MIN_STRATUM = 8


def weighted_premium(pools: list[tuple[list[float], list[float]]]) -> float | None:
    """Weighted mean of per-stratum median ratios, as a percentage.

    Weighted by the size of the with-pool: a stratum where forty postings ask
    for a skill says more about that skill than one where nine do. Returns
    ``None`` when no stratum has both sides, which is not zero — zero would mean
    "measured, no premium".
    """
    numerator = denominator = 0.0
    for with_pool, without_pool in pools:
        if not with_pool or not without_pool:
            continue
        without_median = median(without_pool)
        if without_median == 0:
            continue
        numerator += (median(with_pool) / without_median) * len(with_pool)
        denominator += len(with_pool)
    return (numerator / denominator - 1) * 100 if denominator else None


def bootstrap_interval(
    pools: list[tuple[list[float], list[float]]],
    rng,
    replicates: int = REPLICATES,
) -> tuple[float | None, float | None]:
    """The 2.5th and 97.5th percentiles of the premium under resampling.

    Returns ``(None, None)`` when fewer than half the replicates produced a
    number. That happens when the strata are so thin that resampling routinely
    empties one side, and reporting an interval built from the survivors would
    quietly describe a different, luckier population.
    """
    estimates: list[float] = []
    draw = rng.choices
    for _ in range(replicates):
        resampled = [
            (draw(with_pool, k=len(with_pool)), draw(without_pool, k=len(without_pool)))
            for with_pool, without_pool in pools
        ]
        value = weighted_premium(resampled)
        if value is not None:
            estimates.append(value)
    if len(estimates) < replicates // 2:
        return None, None
    estimates.sort()
    low = estimates[int(0.025 * (len(estimates) - 1))]
    high = estimates[int(0.975 * (len(estimates) - 1))]
    return round(low, 1), round(high, 1)
