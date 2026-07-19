"""Per-ATS clients + parsers: Greenhouse / Lever / Ashby -> a common job dict (PLAN.md §4, stage 1).

Common normalized job dict keys:
  source, company, job_id, title, location_raw, is_remote, employment_type,
  published_at (UTC), apply_url, description (plain text), raw_compensation (source-specific).
"""


def fetch_greenhouse(client, slug):
    """GET the Greenhouse board; return a list of normalized job dicts (content -> plain text)."""
    raise NotImplementedError


def fetch_lever(client, slug):
    """GET the Lever board; return a list of normalized job dicts. Empty array / 404 -> []."""
    raise NotImplementedError


def fetch_ashby(client, slug):
    """GET the Ashby board with includeCompensation; return a list of normalized job dicts."""
    raise NotImplementedError


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}
