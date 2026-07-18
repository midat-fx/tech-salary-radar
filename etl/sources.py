"""Per-ATS clients + parsers: Greenhouse / Lever / Ashby -> a common job dict (PLAN.md §4, stage 1).

Common normalized job dict keys:
  source, company, job_id (str), title, location_raw, is_remote (bool), employment_type,
  published_at (ISO 8601 UTC str), apply_url, department, description (plain text), raw_compensation.
"""

import html
import re
from datetime import datetime, timezone

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from etl.config import SOURCES

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(text):
    """Unescape entities and strip tags to collapsed plain text."""
    if not text:
        return ""
    return _WS.sub(" ", _TAG.sub(" ", html.unescape(text))).strip()


def _epoch_ms_to_iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


class _Retryable(Exception):
    """Wraps a transient upstream status so tenacity retries it."""


@retry(
    retry=retry_if_exception_type((httpx.TransportError, _Retryable)),
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _get(client, url):
    """GET with retry on transport errors and 429/5xx. 404 -> None (dead board)."""
    resp = client.get(url)
    if resp.status_code == 404:
        return None
    if resp.status_code == 429 or resp.status_code >= 500:
        raise _Retryable(f"{resp.status_code} for {url}")
    resp.raise_for_status()
    return resp.json()


def fetch_greenhouse(client, slug):
    data = _get(client, SOURCES["greenhouse"].format(slug=slug))
    if not data:
        return []
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        depts = j.get("departments") or []
        out.append({
            "source": "greenhouse", "company": slug, "job_id": str(j.get("id")),
            "title": j.get("title") or "", "location_raw": loc,
            "is_remote": "remote" in loc.lower(), "employment_type": None,
            "published_at": j.get("first_published") or j.get("updated_at"),
            "apply_url": j.get("absolute_url"),
            "department": (depts[0].get("name") if depts else None),
            "description": strip_html(j.get("content")), "raw_compensation": None,
        })
    return out


def fetch_lever(client, slug):
    data = _get(client, SOURCES["lever"].format(slug=slug))
    if not data:  # None (404) or [] (empty board)
        return []
    out = []
    for j in data:
        cat = j.get("categories") or {}
        wt = (j.get("workplaceType") or "").lower()
        out.append({
            "source": "lever", "company": slug, "job_id": str(j.get("id")),
            "title": j.get("text") or "", "location_raw": cat.get("location") or "",
            "is_remote": wt == "remote", "employment_type": cat.get("commitment"),
            "published_at": _epoch_ms_to_iso(j.get("createdAt")),
            "apply_url": j.get("hostedUrl"), "department": cat.get("team"),
            "description": j.get("descriptionPlain") or "",
            "raw_compensation": j.get("salaryRange"),
        })
    return out


def fetch_ashby(client, slug):
    data = _get(client, SOURCES["ashby"].format(slug=slug))
    if not data:
        return []
    out = []
    for j in data.get("jobs", []):
        out.append({
            "source": "ashby", "company": slug, "job_id": str(j.get("id")),
            "title": j.get("title") or "", "location_raw": j.get("location") or "",
            "is_remote": bool(j.get("isRemote")), "employment_type": j.get("employmentType"),
            "published_at": j.get("publishedAt"), "apply_url": j.get("jobUrl"),
            "department": j.get("department"),
            "description": j.get("descriptionPlain") or "",
            "raw_compensation": j.get("compensation"),
        })
    return out


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}
