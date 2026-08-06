"""One HTTP call to a board, with the retry policy all three share.

The boards fail in the same three ways and want the same three answers:

* **404** — the board was deleted or renamed. Not an error: the seed list is
  months old and companies churn. Returns ``None`` so the caller contributes
  nothing and moves on.
* **429 / 5xx** — transient. Retried with a stated backoff, because a single
  slow board must not cost the crawl and a burst of 429s usually clears.
* **anything else** — raised, so the caller's circuit breaker can count it.

The backoff is a list of numbers and the wait goes through the injected
:class:`~etl.clock.Sleeper`. It used to be a ``tenacity`` decorator, which was
shorter and hid a real ``time.sleep`` from the determinism guard — the suite
spent fifteen real seconds proving that five attempts happen.
"""

from __future__ import annotations

import httpx

from etl.clock import Sleeper, SystemSleeper
from etl.config import HTTP_TIMEOUT, USER_AGENT

__all__ = ["Transient", "get_json", "build_client", "BACKOFF_SECONDS", "MAX_ATTEMPTS"]

#: Waits between attempts, in seconds. Five attempts, doubling. Past that the
#: board is not slow, it is down, and the circuit breaker is the right tool.
BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)
MAX_ATTEMPTS = len(BACKOFF_SECONDS) + 1


class Transient(Exception):
    """A status worth trying again: 429 or 5xx."""


def build_client(base_url: str | None = None) -> httpx.Client:
    """An httpx client identifying this project, with the configured timeout.

    The User-Agent carries a contact address on purpose: these are public
    endpoints used without a key, and a board owner who wants the crawl to stop
    should be able to say so without filing an abuse report.
    """
    kwargs: dict[str, object] = {
        "headers": {"User-Agent": USER_AGENT},
        "timeout": HTTP_TIMEOUT,
        "follow_redirects": True,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return httpx.Client(**kwargs)


def _attempt(client, url: str):
    response = client.get(url)
    if response.status_code == 404:
        return None
    if response.status_code == 429 or response.status_code >= 500:
        raise Transient(f"{response.status_code} for {url}")
    response.raise_for_status()
    return response.json()


def get_json(client, url: str, sleeper: Sleeper | None = None):
    """GET and decode JSON. ``None`` for 404; retries 429, 5xx and transport errors."""
    sleeper = sleeper or SystemSleeper()
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return _attempt(client, url)
        except (httpx.TransportError, Transient) as exc:
            last = exc
            if attempt < len(BACKOFF_SECONDS):
                sleeper.sleep(BACKOFF_SECONDS[attempt])
    assert last is not None
    raise last
