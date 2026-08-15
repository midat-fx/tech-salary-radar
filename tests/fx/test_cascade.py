"""Three sources, tried in order, and the one failure that must not be quiet."""

from __future__ import annotations

import json

import httpx
import pytest

from etl.fx import ER_API, FxError, RateTable, cache_path, fetch_rates, read_cache, to_usd
from etl.testing import FixedClock

RATES = {"USD": 1.0, "GBP": 0.8, "EUR": 0.9}


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def er_api_ok(request):
    if str(request.url) == ER_API:
        return httpx.Response(200, json={"result": "success", "rates": {"GBP": 0.8, "EUR": 0.9}})
    return httpx.Response(500)


def all_dead(request):
    return httpx.Response(503)


class TestConvert:
    def test_usd_passes_through(self):
        assert to_usd(100_000, "USD", RATES) == 100_000
        assert to_usd(100_000, None, RATES) == 100_000

    def test_a_rate_divides_because_rates_are_units_per_usd(self):
        assert to_usd(80_000, "GBP", RATES) == pytest.approx(100_000)

    def test_an_unknown_currency_yields_nothing_rather_than_the_raw_number(self):
        # Returning the amount unchanged turns a 12,000,000 JPY salary into a
        # twelve-million-dollar one, which then survives every plausibility
        # check because it is a number.
        assert to_usd(12_000_000, "JPY", RATES) is None

    def test_it_works_against_a_table_object_too(self):
        assert to_usd(80_000, "GBP", RateTable({"GBP": 0.8})) == pytest.approx(100_000)


class TestRateTable:
    def test_usd_is_always_one_whatever_the_source_said(self):
        # A source stating it wrongly would silently rescale every US salary.
        assert RateTable({"USD": 1.7, "GBP": 0.8}).get("USD") == 1.0

    def test_lookup_is_case_insensitive(self):
        assert RateTable({"GBP": 0.8}).get("gbp") == 0.8

    def test_membership_reads_naturally(self):
        assert "GBP" in RateTable({"GBP": 0.8})
        assert "JPY" not in RateTable({"GBP": 0.8})

    def test_a_fresh_table_is_not_stale(self):
        clock = FixedClock()
        table = RateTable({"GBP": 0.8}, day=clock.now().date().isoformat())
        assert not table.is_stale(clock.now())
        assert table.age(clock.now()) == 0

    def test_an_old_table_is_stale(self):
        clock = FixedClock()
        table = RateTable({"GBP": 0.8}, day="2026-08-01")
        assert table.is_stale(clock.now())

    def test_an_undated_table_is_stale_by_definition(self):
        # Every non-USD figure was converted with something; the page should say
        # the rate is unknown rather than imply it was current.
        assert RateTable({"GBP": 0.8}).is_stale(FixedClock().now())

    def test_the_description_names_the_source_and_the_day(self):
        line = RateTable({"GBP": 0.8}, day="2026-08-19", source="er-api").describe()
        assert "2026-08-19" in line and "er-api" in line and "GBP" in line


class TestCascade:
    def test_the_first_source_wins(self, tmp_path):
        table = fetch_rates(client_for(er_api_ok), tmp_path, FixedClock())
        assert table.source == "er-api"
        assert table.get("GBP") == 0.8

    def test_a_live_fetch_refreshes_the_cache(self, tmp_path):
        fetch_rates(client_for(er_api_ok), tmp_path, FixedClock())
        cached = json.loads(cache_path(tmp_path).read_text())
        assert cached["date"] == "2026-08-19"
        assert cached["rates"]["GBP"] == 0.8

    def test_the_cache_is_the_third_source_when_both_endpoints_are_dead(self, tmp_path):
        fetch_rates(client_for(er_api_ok), tmp_path, FixedClock())
        table = fetch_rates(client_for(all_dead), tmp_path, FixedClock())
        assert table.source == "cache"
        assert table.get("GBP") == 0.8

    def test_the_cache_is_not_rewritten_from_itself(self, tmp_path):
        # Rewriting it would move its date forward and make a stale table look
        # current, which is the one thing the staleness flag exists to prevent.
        clock = FixedClock()
        fetch_rates(client_for(er_api_ok), tmp_path, clock)
        clock.advance(days=10)
        fetch_rates(client_for(all_dead), tmp_path, clock)
        assert json.loads(cache_path(tmp_path).read_text())["date"] == "2026-08-19"

    def test_everything_dead_and_no_cache_raises(self, tmp_path):
        # An empty table converts nothing, and a day where every non-USD posting
        # silently lost its salary looks like a day nobody in Europe published one.
        with pytest.raises(FxError, match="no usable cache"):
            fetch_rates(client_for(all_dead), tmp_path, FixedClock())

    def test_a_corrupt_cache_is_not_a_usable_cache(self, tmp_path):
        cache_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        cache_path(tmp_path).write_text("{not json")
        assert read_cache(tmp_path) is None
        with pytest.raises(FxError):
            fetch_rates(client_for(all_dead), tmp_path, FixedClock())

    def test_an_empty_cache_is_not_a_usable_cache(self, tmp_path):
        cache_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        cache_path(tmp_path).write_text(json.dumps({"date": "2026-08-01", "rates": {}}))
        assert read_cache(tmp_path) is None
