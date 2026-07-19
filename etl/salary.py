"""Parse and normalize salary to annual gross USD (PLAN.md §5, stage 2).

Ashby: structured `compensation` components (Salary) or scrapeable summary string.
Lever: `salaryRange` field. Greenhouse: regex over description text (US pay-transparency, sparse).
"""

import re

from etl.config import (
    HOURS_PER_YEAR,
    MONTHS_PER_YEAR,
    SALARY_MAX_USD,
    SALARY_MIN_USD,
    WEEKS_PER_YEAR,
)
from etl.fx import to_usd

# Run-scoped parser diagnostics, merged into data/cache/last_run.json by cli.run().
STATS = {"gh_pairs_rejected": 0, "ashby_currency_conflicts": 0, "ratio_guard_dropped": 0}


def reset_stats():
    for k in STATS:
        STATS[k] = 0


SYMBOL_CUR = {"$": "USD", "£": "GBP", "€": "EUR"}
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)"
_SEP = r"\s*(?:-|–|—|to|до)\s*"
# "$150,000 - $180,000", "£85,000 – £100,000", "$150-200K", "€70.000 - €90.000"
_PAIR = re.compile(rf"([$£€])?\s?{_NUM}\s*([KkMm])?{_SEP}(?:[$£€])?\s?{_NUM}\s*([KkMm])?")
# "GBP 90,000 - 110,000"
_PAIR_CODE = re.compile(rf"\b(USD|GBP|EUR)\b\s*{_NUM}\s*([KkMm])?{_SEP}{_NUM}\s*([KkMm])?", re.I)
_ANCHOR = re.compile(r"(salary|base pay|pay range|compensation|annual|remuneration)", re.I)
_PER_MONTH = re.compile(r"(per month|/month|pro monat|monthly|в месяц)", re.I)
ANCHOR_WINDOW = 150


def _money_to_num(raw, suffix=None):
    """'150,000' / '70.000' / '211.4'+'K' -> float."""
    raw = raw.strip()
    s = (suffix or "").lower()
    # European thousands dot: 70.000 (three trailing digits, no suffix) -> 70000
    if re.fullmatch(r"\d{1,3}\.\d{3}", raw) and not s:
        val = float(raw.replace(".", ""))
    else:
        val = float(raw.replace(",", ""))
    if s == "k":
        val *= 1000
    elif s == "m":
        val *= 1_000_000
    return val


def _pair_from_match(m, code_form=False):
    """-> (lo, hi, currency). Propagates a K/M suffix from hi onto a bare lo ('$150-200K')."""
    if code_form:
        cur, lo_raw, lo_suf, hi_raw, hi_suf = m.group(1).upper(), *m.groups()[1:]
    else:
        sym, lo_raw, lo_suf, hi_raw, hi_suf = m.groups()
        cur = SYMBOL_CUR.get(sym or "$", "USD")
    if hi_suf and not lo_suf:
        lo_suf = hi_suf                      # "$150-200K" -> both in thousands
    return _money_to_num(lo_raw, lo_suf), _money_to_num(hi_raw, hi_suf), cur


def _find_pair(text):
    """First (lo, hi, currency) in text. Code form first — 'GBP 90,000-110,000' has no symbol
    and would otherwise be swallowed by the generic pattern and mislabelled USD."""
    m = _PAIR_CODE.search(text or "")
    if m:
        return _pair_from_match(m, code_form=True)
    m = _PAIR.search(text or "")
    if m:
        return _pair_from_match(m)
    return None


def _plausible(lo, hi):
    """Reject bonus/401k/funding noise: both bounds sane and the range not absurdly wide."""
    if lo is None or hi is None or lo <= 0:
        return False
    if not (20_000 <= lo <= SALARY_MAX_USD and 20_000 <= hi <= SALARY_MAX_USD):
        return False
    return hi / lo <= 3


def _parse_summary(text):
    """Parse a scrapeable range like '$211.4K - $290.6K' -> {min,max,currency,interval}."""
    found = _find_pair(text or "")
    if not found:
        return None
    lo, hi, cur = found
    interval = "month" if _PER_MONTH.search(text or "") else "year"
    return {"min": lo, "max": hi, "currency": cur, "interval": interval}


def _parse_ashby(comp):
    """Per-tier parse: never mix currencies across tiers (a USD min + a JPY max is not a range)."""
    if not comp:
        return None
    tiers = []
    for tier in comp.get("compensationTiers") or []:
        for c in tier.get("components") or []:
            if c.get("compensationType") != "Salary":
                continue
            if c.get("minValue") is None and c.get("maxValue") is None:
                continue
            tiers.append({"min": c.get("minValue"), "max": c.get("maxValue"),
                          "currency": (c.get("currencyCode") or "USD").upper(),
                          "interval": c.get("interval") or "year"})
    if not tiers:
        return _parse_summary(comp.get("scrapeableCompensationSalarySummary"))
    currencies = {t["currency"] for t in tiers}
    if len(currencies) > 1:
        STATS["ashby_currency_conflicts"] += 1
    pick = "USD" if "USD" in currencies else tiers[0]["currency"]
    same = [t for t in tiers if t["currency"] == pick]
    mins = [t["min"] for t in same if t["min"] is not None]
    maxs = [t["max"] for t in same if t["max"] is not None]
    return {"min": min(mins) if mins else None, "max": max(maxs) if maxs else None,
            "currency": pick, "interval": same[0]["interval"]}


def _parse_greenhouse(text):
    """Anchored pair search: a range must sit next to salary wording, not be the first two $ in the ad.

    Guards against '$2,000 401k match', '$1,000,000 OTE' and '$100,000,000 raised' being read as pay.
    """
    text = text or ""
    for anchor in _ANCHOR.finditer(text):
        window = text[max(0, anchor.start() - ANCHOR_WINDOW): anchor.end() + ANCHOR_WINDOW]
        found = _find_pair(window)
        if not found:
            continue
        lo, hi, cur = found
        if lo > hi:
            lo, hi = hi, lo
        interval = "month" if _PER_MONTH.search(window) else "year"
        # judge plausibility on the annualised figures: a monthly EUR 5,000-6,000 band is valid
        if not _plausible(to_annual(lo, interval), to_annual(hi, interval)):
            STATS["gh_pairs_rejected"] += 1
            continue
        return {"min": lo, "max": hi, "currency": cur, "interval": interval}
    return None


def parse_salary(job):
    """Extract {min, max, currency, interval} from a normalized job by its source, or None."""
    src = job.get("source")
    if src == "ashby":
        return _parse_ashby(job.get("raw_compensation"))
    if src == "lever":
        sr = job.get("raw_compensation")
        if sr and (sr.get("min") or sr.get("max")):
            return {"min": sr.get("min"), "max": sr.get("max"),
                    "currency": sr.get("currency") or "USD", "interval": sr.get("interval") or "year"}
        return None
    if src == "greenhouse":
        return _parse_greenhouse(job.get("description"))
    return None


def to_annual(amount, interval):
    """Scale an amount to annual: hour x2080, week x52, month x12, day x260, year x1."""
    if amount is None:
        return None
    s = (interval or "year").lower()
    if "hour" in s:
        return amount * HOURS_PER_YEAR
    if "week" in s:
        return amount * WEEKS_PER_YEAR
    if "month" in s:
        return amount * MONTHS_PER_YEAR
    if "day" in s:
        return amount * 260
    return amount


def normalize_salary(job, rates):
    """parse -> annual -> USD -> mid (COALESCE) -> sanity bounds (PLAN.md §5).

    Returns dict: salary_min_usd, salary_max_usd, salary_mid_usd, has_salary, dropped_oob,
    plus original currency/min/max/interval for the jobs table.
    """
    blank = {"salary_min_usd": None, "salary_max_usd": None, "salary_mid_usd": None,
             "has_salary": False, "dropped_oob": False, "currency_original": None,
             "salary_min_orig": None, "salary_max_orig": None, "salary_interval_orig": None}
    s = parse_salary(job)
    if not s:
        return blank
    currency, interval = s.get("currency") or "USD", s.get("interval") or "year"
    lo = to_usd(to_annual(s.get("min"), interval), currency, rates)
    hi = to_usd(to_annual(s.get("max"), interval), currency, rates)
    if lo is not None and hi is not None:
        mid = (lo + hi) / 2
    else:
        mid = lo if lo is not None else hi
    orig = {"currency_original": currency, "salary_min_orig": s.get("min"),
            "salary_max_orig": s.get("max"), "salary_interval_orig": interval}
    if mid is None:
        return {**blank, **orig}
    # canary for mixed-currency / mis-parsed ranges that survived everything above
    if lo and hi and hi / lo > 20:
        STATS["ratio_guard_dropped"] += 1
        return {**blank, **orig, "dropped_oob": True}
    if mid < SALARY_MIN_USD or mid > SALARY_MAX_USD:
        return {**blank, **orig, "dropped_oob": True}
    return {"salary_min_usd": lo, "salary_max_usd": hi, "salary_mid_usd": mid,
            "has_salary": True, "dropped_oob": False, **orig}
