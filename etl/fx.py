"""FX rates cascade (hh dictionaries -> er-api -> jsdelivr -> cache) and gross->net->KZT (PLAN.md §5)."""


class FxError(RuntimeError):
    """Raised when every FX source is dead and no usable cache exists."""


def fetch_rates(client, data_dir):
    """Resolve KZT-per-currency rates via the source cascade; refresh the cache on success."""
    raise NotImplementedError


def gross_to_net(amount, currency, gross):
    """KZT gross ->x0.90, RUB gross ->x0.87; gross in {false,null} or other currency as-is."""
    raise NotImplementedError


def to_kzt(amount, currency, rates):
    """Convert an amount in the given currency to KZT using resolved rates."""
    raise NotImplementedError


def apply_fx(rows, rates):
    """Fill salary_kzt_net_from / salary_kzt_net_to: gross->net in source currency, then ->KZT."""
    raise NotImplementedError
