"""Seed-list crawl: iterate companies -> per-ATS clients -> normalized jobs (PLAN.md §3.1, stage 1)."""

from etl.config import FETCH_CIRCUIT_BREAK, FETCH_PAUSE_SEC
from etl.clock import SystemSleeper
from etl.rng import Jitter
from etl.sources import FETCHERS, build_client, load_seed


def make_client(base_url=None):
    """Build an httpx.Client with the config User-Agent and HTTP_TIMEOUT."""
    return build_client(base_url)


def iter_jobs(client, seed, pause=FETCH_PAUSE_SEC, log=None, sleeper=None, rng=None):
    """Walk the seed (one request per board, pause + jitter), yield normalized job dicts.

    A dead/empty board contributes nothing; failures are logged and skipped, never fatal.
    The pause between boards goes through an injected sleeper and a seeded jitter, so a test
    walks 320 boards without waiting and without a random schedule (ADR 0007).
    """
    sleeper = sleeper or SystemSleeper()
    jitter = Jitter(base_seconds=pause, rng=rng)
    consecutive_failures, down = {}, set()
    for i, entry in enumerate(seed):
        source = entry["source"]
        fetcher = FETCHERS.get(source)
        if fetcher is None or source in down:
            continue
        try:
            jobs = fetcher(client, entry["slug"])
            consecutive_failures[source] = 0
        except Exception as exc:  # one bad board must not kill the crawl
            consecutive_failures[source] = consecutive_failures.get(source, 0) + 1
            if log:
                log(f"fetch failed {source}:{entry['slug']}: {exc}")
            # a whole ATS being down (429 storm) should not cost hours of retries per board
            if consecutive_failures[source] >= FETCH_CIRCUIT_BREAK:
                down.add(source)
                if log:
                    log(f"{source}: {FETCH_CIRCUIT_BREAK} consecutive failures — skipping its boards")
            jobs = []
        yield from jobs
        if pause and i + 1 < len(seed):
            sleeper.sleep(jitter.next_pause())


__all__ = ["iter_jobs", "load_seed", "make_client"]
