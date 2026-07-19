"""Salary parsing/normalization to annual gross USD (PLAN.md §5, stage 2)."""

from etl.salary import _parse_summary, normalize_salary, parse_salary, to_annual

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


# --- golden cases lifted from production text (PLAN improvements 1.2 / 1.3 / 1.9) ---

def _gh(text):
    return parse_salary({"source": "greenhouse", "description": text})


def test_pair_understands_commas_and_suffix_propagation():
    assert _parse_summary("$150,000 - $180,000") == {
        "min": 150000.0, "max": 180000.0, "currency": "USD", "interval": "year"}
    s = _parse_summary("$150-200K")           # bare lo inherits hi's K
    assert s["min"] == 150000.0 and s["max"] == 200000.0


def test_greenhouse_ignores_funding_and_benefit_amounts():
    # amplitude-style: a $2,000 perk must not become the bottom of the band
    assert _gh("We offer a $2,000 wellness stipend. Salary range: $150,000 - $190,000.") == {
        "min": 150000.0, "max": 190000.0, "currency": "USD", "interval": "year"}
    # funding sentence before the real range
    assert _gh("We raised $100,000,000 in Series C. Salary range: $150,000-$180,000")["min"] == 150000.0
    # databricks-style OTE blowout: 12x spread next to salary wording -> rejected, not averaged
    assert _gh("Annual compensation: $80,000 - $1,000,000 OTE uncapped") is None
    # a lone amount is never a range
    assert _gh("Base salary of $180,000 plus equity") is None


def test_greenhouse_requires_salary_anchor():
    assert _gh("Our customers saved $250,000 - $400,000 last year using the platform") is None


def test_eu_currencies_parsed_and_converted():
    gbp = _gh("Salary: £85,000 - £100,000 per annum")
    assert gbp["currency"] == "GBP" and gbp["min"] == 85000.0
    eur = _gh("Compensation: €70.000 - €90.000")          # european thousands dot
    assert eur["currency"] == "EUR" and eur["min"] == 70000.0 and eur["max"] == 90000.0
    code = _gh("Base salary GBP 90,000 - 110,000")
    assert code["currency"] == "GBP" and code["max"] == 110000.0
    r = normalize_salary({"source": "greenhouse",
                          "description": "Salary: £80,000 - £96,000"}, RATES)
    assert r["has_salary"] and r["salary_min_usd"] == 100000.0   # 80000 / 0.8


def test_monthly_wording_is_annualised():
    s = _gh("Salary range: €5,000 - €6,000 per month")
    assert s["interval"] == "month"


def test_ashby_never_mixes_currencies_across_tiers():
    """Real row: a USD tier and a JPY tier produced min 92k / max 119,000,000 (ratio 1293)."""
    comp = {"compensationTiers": [
        {"components": [{"compensationType": "Salary", "interval": "1 YEAR",
                         "currencyCode": "USD", "minValue": 92000, "maxValue": 115000}]},
        {"components": [{"compensationType": "Salary", "interval": "1 YEAR",
                         "currencyCode": "JPY", "minValue": 95000000, "maxValue": 119000000}]}]}
    s = parse_salary({"source": "ashby", "raw_compensation": comp})
    assert s["currency"] == "USD" and s["min"] == 92000 and s["max"] == 115000


def test_absurd_ratio_is_dropped_by_guard():
    comp = {"compensationTiers": [{"components": [
        {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
         "minValue": 50000, "maxValue": 5_000_000}]}]}
    r = normalize_salary({"source": "ashby", "raw_compensation": comp}, RATES)
    assert not r["has_salary"] and r["dropped_oob"]


def test_no_salary_returns_blank():
    assert normalize_salary({"source": "greenhouse", "description": "No numbers here."}, RATES)[
        "has_salary"] is False
