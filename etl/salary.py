"""Per-source pay extraction, on top of :mod:`etl.money`.

Each board says what it pays in a different place, and only that difference
lives here — the rules about currencies, periods, plausibility and conversion
are the same for all three and belong to :mod:`etl.money`.

* **Ashby** sends structured compensation components, sometimes several tiers,
  occasionally in different currencies; failing that, a scrapeable summary
  string.
* **Lever** sends a ``salaryRange`` object straight from a form.
* **Greenhouse** sends nothing. US pay-transparency law put the range into the
  description text, so it has to be read out of the ad.
"""

from __future__ import annotations

from etl.money import (
    Confidence,
    CurrencyGuess,
    Interval,
    PayRange,
    Verdict,
    convert_range,
    find_anchored_range,
    find_range,
    from_code,
    judge_parsed,
    to_annual,
)
from etl.money.interval import _as_interval

__all__ = [
    "STATS",
    "normalize_salary",
    "parse_salary",
    "reset_stats",
    "to_annual",
]

#: Run-scoped parser diagnostics, merged into ``data/cache/last_run.json``.
#: One counter per verdict plus the two source-specific oddities worth watching:
#: a run whose rejects move is a board changing its format.
STATS: dict[str, int] = {
    "gh_pairs_rejected": 0,
    "ashby_currency_conflicts": 0,
    "ratio_guard_dropped": 0,
    **{f"pay_{verdict.value.replace('-', '_')}": 0 for verdict in Verdict},
}


def reset_stats() -> None:
    for key in STATS:
        STATS[key] = 0


def _bump(name: str) -> None:
    STATS[name] = STATS.get(name, 0) + 1


def _parse_summary(text: str | None) -> PayRange | None:
    """Ashby's human-readable fallback: ``$211.4K - $290.6K``."""
    return find_range(text, origin="ashby-summary")


def _parse_ashby(comp: dict | None) -> PayRange | None:
    """Per-tier parse. Never mixes currencies: a USD floor with a JPY ceiling is
    not a range, and averaging the two produces a number with no meaning."""
    if not comp:
        return None
    tiers = []
    for tier in comp.get("compensationTiers") or []:
        for component in tier.get("components") or []:
            if component.get("compensationType") != "Salary":
                continue
            if component.get("minValue") is None and component.get("maxValue") is None:
                continue
            tiers.append(
                {
                    "min": component.get("minValue"),
                    "max": component.get("maxValue"),
                    "currency": (component.get("currencyCode") or "USD").upper(),
                    "interval": component.get("interval") or "year",
                }
            )
    if not tiers:
        return _parse_summary(comp.get("scrapeableCompensationSalarySummary"))

    currencies = {t["currency"] for t in tiers}
    if len(currencies) > 1:
        _bump("ashby_currency_conflicts")
    # USD wins when present because it is the one currency every rate table has;
    # otherwise the first tier's, which is the one the board listed first.
    picked = "USD" if "USD" in currencies else tiers[0]["currency"]
    same = [t for t in tiers if t["currency"] == picked]
    lows = [t["min"] for t in same if t["min"] is not None]
    highs = [t["max"] for t in same if t["max"] is not None]
    return PayRange(
        min(lows) if lows else None,
        max(highs) if highs else None,
        from_code(picked),
        _as_interval(same[0]["interval"]),
        "ashby-structured",
    )


def _parse_lever(raw: dict | None) -> PayRange | None:
    """Lever's form-filled range. The bounds arrive in whatever order they were typed."""
    if not raw or not (raw.get("min") or raw.get("max")):
        return None
    return PayRange(
        raw.get("min"),
        raw.get("max"),
        from_code(raw.get("currency") or "USD"),
        _as_interval(raw.get("interval") or "year"),
        "lever-field",
    )


def _accept(candidate: PayRange) -> bool:
    """Plausibility as a search predicate, so an implausible match at one anchor
    does not hide the real range at the next one."""
    if judge_parsed(candidate).accepted:
        return True
    _bump("gh_pairs_rejected")
    return False


def _parse_greenhouse(text: str | None) -> PayRange | None:
    """Anchored search over the ad, skipping bands that cannot be pay.

    Rejections are counted: a jump in that count is a board changing its
    wording, not the market changing what it pays.
    """
    return find_anchored_range(text, accept=_accept)


_PARSERS = {
    "ashby": lambda job: _parse_ashby(job.get("raw_compensation")),
    "lever": lambda job: _parse_lever(job.get("raw_compensation")),
    "greenhouse": lambda job: _parse_greenhouse(job.get("description")),
}


def parse_salary(job) -> dict | None:
    """The posted range for a job, in the board's own currency and period.

    Returns the legacy dict shape (``min``/``max``/``currency``/``interval``) so
    the existing callers and their tests keep working; :func:`parsed_range`
    gives the same thing as a :class:`~etl.money.PayRange`.
    """
    found = parsed_range(job)
    if found is None:
        return None
    return {
        "min": found.low,
        "max": found.high,
        "currency": found.currency.code,
        "interval": found.interval.value,
    }


def parsed_range(job) -> PayRange | None:
    """The posted range as a value object, with its origin and currency confidence."""
    parser = _PARSERS.get(job.get("source"))
    return parser(job) if parser else None


def normalize_salary(job, rates) -> dict:
    """Parse, annualise, convert and judge — the stored salary columns for one job.

    Every refusal is counted by its reason. The old code counted two of them and
    lumped everything else into a single out-of-bounds flag, which made a board
    changing its format look exactly like the market moving.
    """
    parsed = parsed_range(job)
    result = convert_range(parsed, rates)
    verdict = result.judgement.verdict
    _bump(f"pay_{verdict.value.replace('-', '_')}")
    if verdict is Verdict.IMPLAUSIBLE_SPREAD:
        _bump("ratio_guard_dropped")
    return result.to_row()


def blank_salary() -> dict:
    """The columns a job with no posted pay contributes."""
    return convert_range(None, {}).to_row()


# Re-exported for callers that only need the vocabulary.
__all__ += ["Confidence", "CurrencyGuess", "Interval", "PayRange", "Verdict", "parsed_range"]
