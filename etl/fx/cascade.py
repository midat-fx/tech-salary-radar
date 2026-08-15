"""Three ways to learn today's rates, tried in order, with the cache last.

Two public endpoints and a file. Neither endpoint is under anyone's control and
both have gone down for a day at a time, so the cache is not an optimisation —
it is the third source, and the only one that cannot fail for a reason outside
this repository.

What the cascade must never do is give up quietly. A run with no rates converts
nothing, so every GBP and EUR posting silently loses its salary and the day's
coverage halves without anything looking broken. That is why the exhausted case
raises.
"""

from __future__ import annotations

import json
from pathlib import Path

from etl.clock import SystemClock, iso_day
from etl.fx.rates import RateTable

__all__ = ["FxError", "ER_API", "JSDELIVR", "fetch_rates", "cache_path", "read_cache", "SOURCES"]

ER_API = "https://open.er-api.com/v6/latest/USD"
JSDELIVR = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"

SOURCES = ("er-api", "jsdelivr", "cache")


class FxError(RuntimeError):
    """Every source is dead and no usable cache exists.

    Raised rather than returning an empty table: an empty table converts
    nothing, and a day where every non-USD posting silently lost its salary
    looks exactly like a day where nobody in Europe published one.
    """


def cache_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "cache" / "fx_latest.json"


def read_cache(data_dir: str | Path) -> RateTable | None:
    """The last table that was successfully fetched, if there is one."""
    path = cache_path(data_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    rates = raw.get("rates")
    if not isinstance(rates, dict) or not rates:
        return None
    return RateTable(
        {code.upper(): float(value) for code, value in rates.items()},
        day=raw.get("date"),
        source="cache",
    )


def _from_er_api(client) -> dict[str, float] | None:
    try:
        payload = client.get(ER_API).json()
    except Exception:  # noqa: BLE001 - any failure means try the next source
        return None
    if payload.get("result") == "success" and payload.get("rates"):
        return {code.upper(): float(value) for code, value in payload["rates"].items()}
    return None


def _from_jsdelivr(client) -> dict[str, float] | None:
    try:
        payload = client.get(JSDELIVR).json()
    except Exception:  # noqa: BLE001
        return None
    table = payload.get("usd") or {}
    return {code.upper(): float(value) for code, value in table.items()} if table else None


def fetch_rates(client, data_dir, clock=None) -> RateTable:
    """Resolve today's rates, refreshing the cache when a live source answers.

    The cache is written only on a live fetch. Rewriting it from itself would
    move its date forward and make a stale table look current, which is the one
    thing the staleness flag exists to prevent.
    """
    clock = clock or SystemClock()
    for name, fetch in (("er-api", _from_er_api), ("jsdelivr", _from_jsdelivr)):
        rates = fetch(client)
        if rates:
            table = RateTable(rates, day=iso_day(clock.now()), source=name)
            path = cache_path(data_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"date": table.day, "rates": table.rates}))
            return table
    cached = read_cache(data_dir)
    if cached is not None:
        return cached
    raise FxError("all FX sources are dead and no usable cache exists")
