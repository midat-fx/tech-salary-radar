"""Seed-list crawl: iterate companies -> per-ATS clients -> normalized jobs (PLAN.md §3.1, stage 1)."""

import json
import random
import time
from pathlib import Path

import httpx

from etl.config import (
    FETCH_CIRCUIT_BREAK,
    FETCH_PAUSE_SEC,
    HTTP_TIMEOUT,
    SEED_PATH,
    USER_AGENT,
)
from etl.sources import FETCHERS


def make_client(base_url=None):
    """Build an httpx.Client with the config User-Agent and HTTP_TIMEOUT."""
    kwargs = {"headers": {"User-Agent": USER_AGENT}, "timeout": HTTP_TIMEOUT,
              "follow_redirects": True}
    if base_url:
        kwargs["base_url"] = base_url
    return httpx.Client(**kwargs)


def load_seed(path=None):
    """Load the seed file -> list of active {source|ats, slug, name} entries only."""
    raw = json.loads(Path(path or SEED_PATH).read_text())
    seed = []
    for e in raw:
        if e.get("status") == "active":
            seed.append({"source": e.get("ats") or e.get("source"),
                         "slug": e["slug"], "name": e.get("name", e["slug"])})
    return seed


def iter_jobs(client, seed, pause=FETCH_PAUSE_SEC, log=None):
    """Walk the seed (one request per board, pause + jitter), yield normalized job dicts.

    A dead/empty board contributes nothing; failures are logged and skipped, never fatal.
    """
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
            time.sleep(pause + random.uniform(0.2, 0.4))
