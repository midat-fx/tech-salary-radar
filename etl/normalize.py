"""Turn raw hh items into snapshot / new-vacancy rows and write daily parquet partitions (stage 2)."""


def strip_tags(html):
    """Unescape HTML entities and strip tags to plain text."""
    raise NotImplementedError


def normalize_currency(code):
    """Normalize hh currency codes: RUR -> RUB, BYR -> BYN; pass others through."""
    raise NotImplementedError


def normalize_item(item, search_key, source_area):
    """Normalize one hh item (salary_range with fallback to salary, MONTH mode only)."""
    raise NotImplementedError


def build_snapshot_rows(items):
    """Build thin snapshot rows for all active vacancies found today."""
    raise NotImplementedError


def build_new_vacancy_rows(items):
    """Build full rows for ids first seen today (dedup by vacancy_id, SEARCH_KEYS priority)."""
    raise NotImplementedError


def write_partition(rows, data_dir, table, dt):
    """Write a daily parquet partition (zstd), overwriting the whole day = idempotency."""
    raise NotImplementedError
