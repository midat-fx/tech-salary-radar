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

_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*[KkMm])")
_PAIR = re.compile(r"\$\s?([\d.]+)\s*([KkMm])?\s*[-–—to]+\s*\$?\s?([\d.]+)\s*([KkMm])?")


def _money_to_num(raw, suffix=None):
    """'150,000' / '211.4' + 'K' -> float USD."""
    val = float(raw.replace(",", "").strip())
    s = (suffix or "").lower()
    if s == "k" or (val < 1000 and "," not in raw):
        val *= 1000 if s == "k" else 1
    if s == "m":
        val *= 1_000_000
    return val


def _parse_summary(text):
    """Parse a scrapeable range like '$211.4K - $290.6K' -> (min, max)."""
    m = _PAIR.search(text or "")
    if not m:
        return None
    lo = _money_to_num(m.group(1), m.group(2))
    hi = _money_to_num(m.group(3), m.group(4))
    return {"min": lo, "max": hi, "currency": "USD", "interval": "year"}


def _parse_ashby(comp):
    if not comp:
        return None
    mins, maxs, currency, interval = [], [], None, None
    for tier in comp.get("compensationTiers") or []:
        for c in tier.get("components") or []:
            if c.get("compensationType") == "Salary":
                if c.get("minValue") is not None:
                    mins.append(c["minValue"])
                if c.get("maxValue") is not None:
                    maxs.append(c["maxValue"])
                currency = currency or c.get("currencyCode")
                interval = interval or c.get("interval")
    if mins or maxs:
        return {"min": min(mins) if mins else None, "max": max(maxs) if maxs else None,
                "currency": currency or "USD", "interval": interval or "year"}
    return _parse_summary(comp.get("scrapeableCompensationSalarySummary"))


def _parse_greenhouse(text):
    tokens = _MONEY.findall(text or "")
    nums = []
    for t in tokens:
        m = re.match(r"([\d.,]+)\s*([KkMm])?", t)
        nums.append(_money_to_num(m.group(1), m.group(2)))
    nums = [n for n in nums if n >= 1000]
    if len(nums) >= 2:
        return {"min": min(nums[:2]), "max": max(nums[:2]), "currency": "USD", "interval": "year"}
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
    if mid < SALARY_MIN_USD or mid > SALARY_MAX_USD:
        return {**blank, **orig, "dropped_oob": True}
    return {"salary_min_usd": lo, "salary_max_usd": hi, "salary_mid_usd": mid,
            "has_salary": True, "dropped_oob": False, **orig}
