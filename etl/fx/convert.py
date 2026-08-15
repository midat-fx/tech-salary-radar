"""Apply a rate table to an amount.

One function, and it exists as its own module because the failure it guards
against is quiet. Returning the amount unchanged when a currency is unknown —
the obvious defensive default — turns a 12,000,000 JPY salary into a
twelve-million-dollar one, which then survives every plausibility check because
it is a number.
"""

from __future__ import annotations

from etl.fx.rates import RateTable

__all__ = ["to_usd", "convert_pair"]


def to_usd(amount: float | None, currency: str | None, rates: RateTable | dict) -> float | None:
    """``amount`` in ``currency`` -> USD. ``None`` when the currency has no rate."""
    if amount is None:
        return None
    code = (currency or "USD").upper()
    if code == "USD":
        return float(amount)
    rate = rates.get(code) if isinstance(rates, RateTable) else rates.get(code)
    if not rate:
        return None
    return float(amount) / rate


def convert_pair(low, high, currency, rates) -> tuple[float | None, float | None]:
    """Both bounds through the same rate, so a band cannot straddle two days."""
    return to_usd(low, currency, rates), to_usd(high, currency, rates)
