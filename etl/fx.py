"""FX rates cascade (er-api base USD -> jsdelivr -> cache), for non-USD -> USD (PLAN.md §5)."""

import json
from datetime import date
from pathlib import Path

ER_API = "https://open.er-api.com/v6/latest/USD"
JSDELIVR = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"


class FxError(RuntimeError):
    """Raised when every FX source is dead and no usable cache exists."""


def _cache_path(data_dir):
    return Path(data_dir) / "cache" / "fx_latest.json"


def fetch_rates(client, data_dir):
    """Resolve 'currency per 1 USD' rates via the source cascade; refresh the cache on success.

    Returns a dict of UPPERCASE currency code -> units per 1 USD (USD == 1.0).
    """
    rates = _from_er_api(client) or _from_jsdelivr(client)
    if rates:
        rates["USD"] = 1.0
        path = _cache_path(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": date.today().isoformat(), "rates": rates}))
        return rates
    cached = _cache_path(data_dir)
    if cached.exists():
        return json.loads(cached.read_text())["rates"]
    raise FxError("all FX sources dead and no cache")


def _from_er_api(client):
    try:
        d = client.get(ER_API).json()
        if d.get("result") == "success" and d.get("rates"):
            return {k.upper(): float(v) for k, v in d["rates"].items()}
    except Exception:
        return None
    return None


def _from_jsdelivr(client):
    try:
        d = client.get(JSDELIVR).json()
        table = d.get("usd") or {}
        if table:
            return {k.upper(): float(v) for k, v in table.items()}
    except Exception:
        return None
    return None


def to_usd(amount, currency, rates):
    """Convert an amount in the given currency to USD (usd = amount / rate_ccy)."""
    if amount is None:
        return None
    if currency in (None, "USD", "usd"):
        return float(amount)
    rate = rates.get((currency or "").upper())
    if not rate:
        return None
    return float(amount) / rate
