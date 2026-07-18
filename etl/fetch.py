"""httpx client for the hh API: paging, depth-splitting, polite backoff (PLAN.md §4, stage 1)."""


class CaptchaError(RuntimeError):
    """Raised on a 403 / captcha_required response from hh vacancy endpoints."""


def make_client(base_url=None):
    """Build an httpx.Client with the config User-Agent and a 20s timeout."""
    raise NotImplementedError


def _get_json(client, path, params=None):
    """GET with tenacity retry (TransportError/429/5xx); 403 -> CaptchaError, no retry."""
    raise NotImplementedError


def search_page(client, query, area, page=0, per_page=None, extra=None):
    """Fetch a single search page and return the parsed JSON body."""
    raise NotImplementedError


def search_all(client, query, area, search_key, source_area):
    """Fetch all pages for a query, depth-splitting by experience/date when found > threshold."""
    raise NotImplementedError


def fetch_details(client, vacancy_ids):
    """Fetch vacancy details up to DETAIL_LIMIT; on CaptchaError return partial with a warning."""
    raise NotImplementedError
