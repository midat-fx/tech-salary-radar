"""The retry policy the three boards share, and the statuses it treats differently."""

from __future__ import annotations

import httpx
import pytest

from etl.sources import MAX_ATTEMPTS, Transient, build_client, get_json
from etl.sources.transport import BACKOFF_SECONDS


class RecordingSleeper:
    """Records the backoff instead of taking it: five real attempts used to cost
    the suite fifteen seconds of wall clock."""

    def __init__(self):
        self.pauses = []

    def sleep(self, seconds):
        self.pauses.append(seconds)


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://board.test")


class TestStatuses:
    def test_a_200_returns_the_decoded_body(self):
        client = client_for(lambda r: httpx.Response(200, json={"jobs": []}))
        assert get_json(client, "https://board.test/x") == {"jobs": []}

    def test_a_404_is_a_dead_board_not_an_error(self):
        # The seed is months old and companies churn; a deleted board must cost
        # nothing but the request.
        client = client_for(lambda r: httpx.Response(404))
        assert get_json(client, "https://board.test/x") is None

    def test_a_403_is_raised_so_the_circuit_breaker_can_count_it(self):
        client = client_for(lambda r: httpx.Response(403))
        with pytest.raises(httpx.HTTPStatusError):
            get_json(client, "https://board.test/x")


class TestRetry:
    def test_a_429_is_retried_and_then_succeeds(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(429) if calls["n"] == 1 else httpx.Response(200, json={"ok": 1})

        sleeper = RecordingSleeper()
        assert get_json(client_for(handler), "https://board.test/x", sleeper) == {"ok": 1}
        assert calls["n"] == 2
        assert sleeper.pauses == [BACKOFF_SECONDS[0]]

    def test_a_persistent_5xx_gives_up_after_the_declared_attempts(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(503)

        sleeper = RecordingSleeper()
        with pytest.raises(Transient):
            get_json(client_for(handler), "https://board.test/x", sleeper)
        assert calls["n"] == MAX_ATTEMPTS
        assert sleeper.pauses == list(BACKOFF_SECONDS)

    def test_a_transport_error_is_retried_too(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ConnectError("refused", request=request)
            return httpx.Response(200, json={"ok": 1})

        assert get_json(client_for(handler), "https://board.test/x", RecordingSleeper()) == {"ok": 1}


class TestClient:
    def test_it_identifies_the_project_and_a_contact(self):
        # These are public endpoints used without a key; a board owner who wants
        # the crawl to stop should be able to say so without filing a report.
        agent = build_client().headers["User-Agent"]
        assert "tech-salary-radar" in agent
        assert "@" in agent

    def test_it_carries_the_configured_timeout(self):
        from etl.config import HTTP_TIMEOUT

        assert build_client().timeout.read == HTTP_TIMEOUT
