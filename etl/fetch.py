"""Seed-list crawl: iterate companies -> per-ATS clients -> normalized jobs (PLAN.md §3.1, stage 1)."""


def make_client(base_url=None):
    """Build an httpx.Client with the config User-Agent and HTTP_TIMEOUT."""
    raise NotImplementedError


def load_seed(path=None):
    """Load data/seed_companies.json -> list of {source, slug, name}."""
    raise NotImplementedError


def iter_jobs(client, seed):
    """Walk the seed list (one request per board, pause + jitter), yield normalized job dicts.

    Tags each job with source/company; a dead/empty board contributes nothing and is logged.
    """
    raise NotImplementedError
