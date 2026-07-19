"""Parse the three ATS formats from live-captured fixtures via httpx.MockTransport (PLAN.md stage 1)."""

from pathlib import Path

import httpx

from etl.sources import fetch_ashby, fetch_greenhouse, fetch_lever

FIX = Path(__file__).parent / "fixtures"
GREENHOUSE = FIX.joinpath("greenhouse.json").read_text()
LEVER = FIX.joinpath("lever.json").read_text()
ASHBY = FIX.joinpath("ashby.json").read_text()


def _handler(request):
    host, path = request.url.host, request.url.path
    if "dead" in path:
        return httpx.Response(404, text='{"error":"not found"}')
    if "greenhouse" in host:
        return httpx.Response(200, text=GREENHOUSE)
    if "lever" in host:
        return httpx.Response(200, text="[]" if "empty" in path else LEVER)
    if "ashby" in host:
        return httpx.Response(200, text=ASHBY)
    return httpx.Response(404)


def _client():
    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_greenhouse_parse():
    jobs = fetch_greenhouse(_client(), "gitlab")
    assert len(jobs) >= 1
    j = jobs[0]
    assert j["source"] == "greenhouse" and j["company"] == "gitlab"
    assert j["title"] and j["description"] and "<" not in j["description"]
    assert isinstance(j["is_remote"], bool) and isinstance(j["job_id"], str)


def test_lever_parse():
    jobs = fetch_lever(_client(), "matchgroup")
    assert len(jobs) >= 1
    j = jobs[0]
    assert j["source"] == "lever" and j["title"]
    assert j["published_at"] is None or j["published_at"].startswith("20")  # epoch ms -> ISO


def test_ashby_parse():
    jobs = fetch_ashby(_client(), "linear")
    assert len(jobs) >= 1
    assert any(j["raw_compensation"] for j in jobs)  # ashby carries structured compensation


def test_dead_board_returns_empty():
    assert fetch_greenhouse(_client(), "dead-slug") == []


def test_empty_lever_board_returns_empty():
    assert fetch_lever(_client(), "empty-co") == []
