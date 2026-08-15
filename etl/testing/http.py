"""An HTTP transport that answers from a script instead of the network.

Built on ``httpx.MockTransport`` so the client under test is the real
:func:`etl.sources.build_client` with its real headers and timeout — the only
thing replaced is the socket. A fake that reimplemented the client would stop
catching the mistakes that live in the client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

__all__ = [
    "FIXTURES",
    "DEFAULT_RATES",
    "RecordedBoard",
    "board_client",
    "board_transport",
    "load_fixture",
]

#: What the fake FX endpoint answers. Every run fetches rates, so a transport
#: that cannot serve them cannot drive a run — and a run is the only place the
#: layers meet.
DEFAULT_RATES = {"GBP": 0.79, "EUR": 0.92}

#: Where the live-captured board payloads live. They were recorded once from the
#: real APIs and committed; nothing in the suite may fetch them again.
FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


def load_fixture(name: str) -> dict | list:
    """A recorded board payload by file name, e.g. ``"greenhouse.json"``."""
    return json.loads((FIXTURES / name).read_text())


@dataclass
class RecordedBoard:
    """What one slug answers with: a payload, or a status to fail with."""

    payload: dict | list | None = None
    status: int = 200

    def response(self) -> httpx.Response:
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(200, json=self.payload if self.payload is not None else {})


@dataclass
class board_transport:  # noqa: N801 - reads as a factory at the call site
    """Route requests by the slug in their URL.

    Anything not scripted answers 404, which is the same thing a board that was
    deleted between the seed being built and today would say — the default is
    the realistic case rather than an error.
    """

    boards: dict[str, RecordedBoard] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)
    rates: dict[str, float] | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if self.rates is not None and ("er-api" in url or "currency-api" in url):
            return httpx.Response(200, json={"result": "success", "rates": self.rates})
        for slug, board in self.boards.items():
            if f"/{slug}" in url or f"={slug}" in url or f"boards/{slug}" in url:
                return board.response()
        return httpx.Response(404)

    @property
    def board_requests(self) -> list[str]:
        """Requests to boards, with the rate lookups filtered out."""
        return [u for u in self.requests if "er-api" not in u and "currency-api" not in u]

    def as_transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    @property
    def call_count(self) -> int:
        return len(self.requests)


def board_client(
    boards: dict[str, RecordedBoard], rates: dict[str, float] | None = DEFAULT_RATES
) -> tuple[httpx.Client, board_transport]:
    """A real client wired to a scripted transport, plus the transport to assert on.

    Rates are served by default. Pass ``rates=None`` to drive the case where
    every FX source is dead, which is the one the cascade raises on.
    """
    handler = board_transport(boards, rates=rates)
    client = httpx.Client(transport=handler.as_transport(), follow_redirects=True)
    return client, handler
