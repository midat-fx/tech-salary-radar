"""Salary parsing/normalization to annual gross USD (PLAN.md §5, stage 2)."""

from etl.salary import normalize_salary, parse_salary, to_annual

RATES = {"USD": 1.0, "GBP": 0.8, "EUR": 0.9}  # units per 1 USD


def _ashby(min_v, max_v, interval="1 YEAR", cur="USD"):
    return {"source": "ashby", "raw_compensation": {"compensationTiers": [
        {"components": [{"compensationType": "Salary", "interval": interval,
                         "currencyCode": cur, "minValue": min_v, "maxValue": max_v}]}]}}


def test_ashby_structured_annual_usd():
    r = normalize_salary(_ashby(211400, 290600), RATES)
    assert r["has_salary"] and r["salary_mid_usd"] == (211400 + 290600) / 2


def test_hourly_scaled_to_annual():
    assert to_annual(100, "1 HOUR") == 208000
    r = normalize_salary(_ashby(100, 120, interval="1 HOUR"), RATES)
    assert r["salary_mid_usd"] == (208000 + 249600) / 2


def test_gbp_converted_to_usd():
    r = normalize_salary(_ashby(80000, 96000, cur="GBP"), RATES)
    # 80000/0.8=100000, 96000/0.8=120000
    assert r["salary_min_usd"] == 100000 and r["salary_max_usd"] == 120000


def test_only_min_coalesces_to_min():
    r = normalize_salary(_ashby(150000, None), RATES)
    assert r["has_salary"] and r["salary_mid_usd"] == 150000


def test_out_of_bounds_dropped():
    low = normalize_salary(_ashby(2000, 4000), RATES)   # < $10k
    high = normalize_salary(_ashby(3_000_000, 4_000_000), RATES)  # > $1.5M
    assert not low["has_salary"] and low["dropped_oob"]
    assert not high["has_salary"] and high["dropped_oob"]


def test_lever_salary_range():
    job = {"source": "lever", "raw_compensation": {
        "interval": "per-year-salary", "currency": "USD", "min": 150000, "max": 180000}}
    r = normalize_salary(job, RATES)
    assert r["has_salary"] and r["salary_mid_usd"] == 165000


def test_greenhouse_regex_from_text():
    job = {"source": "greenhouse",
           "description": "Compensation for this role is $108,400 to $129,600 per year plus equity."}
    s = parse_salary(job)
    assert s and s["min"] == 108400 and s["max"] == 129600


def test_no_salary_returns_blank():
    assert normalize_salary({"source": "greenhouse", "description": "No numbers here."}, RATES)[
        "has_salary"] is False
