"""FX cascade and USD conversion (PLAN.md §5)."""

import json

import httpx

from etl.fx import fetch_rates, to_usd

RATES = {"USD": 1.0, "GBP": 0.8, "EUR": 0.9}


def test_to_usd_passthrough_and_convert():
    assert to_usd(100000, "USD", RATES) == 100000
    assert to_usd(None, "USD", RATES) is None
    assert to_usd(80000, "GBP", RATES) == 100000        # 80000 / 0.8
    assert to_usd(1000, "ZZZ", RATES) is None            # unknown currency


def test_fetch_rates_from_er_api(tmp_path):
    def handler(request):
        if "er-api" in request.url.host:
            return httpx.Response(200, text=json.dumps(
                {"result": "success", "rates": {"USD": 1, "EUR": 0.92, "GBP": 0.79}}))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rates = fetch_rates(client, tmp_path)
    assert rates["EUR"] == 0.92 and rates["USD"] == 1.0
    assert (tmp_path / "cache" / "fx_latest.json").exists()   # cache written
