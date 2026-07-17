"""DuckDB SQL over parquet -> site/data/*.json + badge.json (PLAN.md §3.5, §3.6, stage 6)."""


def aggregate(data_dir, site_data_dir):
    """Build latest.json, timeseries.json, meta.json, badge.json from the parquet history."""
    raise NotImplementedError


def skill_premium(con, source_area):
    """Skill premium per country, stratified by experience bucket (PLAN.md §3.6)."""
    raise NotImplementedError
