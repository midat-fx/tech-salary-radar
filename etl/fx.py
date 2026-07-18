"""FX rates cascade (er-api base USD -> jsdelivr -> cache), for non-USD -> USD (PLAN.md §5)."""


class FxError(RuntimeError):
    """Raised when every FX source is dead and no usable cache exists."""


def fetch_rates(client, data_dir):
    """Resolve 'currency per 1 USD' rates via the source cascade; refresh the cache on success."""
    raise NotImplementedError


def to_usd(amount, currency, rates):
    """Convert an amount in the given currency to USD (usd = amount / rate_ccy)."""
    raise NotImplementedError
