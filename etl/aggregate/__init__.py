"""DuckDB over the parquet history -> the four files the dashboard reads.

Five stages, each its own module and each testable without the others:
:mod:`~etl.aggregate.connection` opens the views, :mod:`~etl.aggregate.labels`
separates "labelled, nothing found" from "never read",
:mod:`~etl.aggregate.snapshot` shapes the day, :mod:`~etl.aggregate.series`
builds the chart, and :mod:`~etl.aggregate.premium` computes the flagship
number with the interval that says how much to trust it.
"""

from __future__ import annotations

import json
from pathlib import Path

from etl.aggregate.bootstrap import MIN_STRATUM, REPLICATES, bootstrap_interval, weighted_premium
from etl.aggregate.connection import open_dataset
from etl.aggregate.labels import LabelIndex, labels_for
from etl.aggregate.meta import (
    ATTRIBUTION,
    BOARD_URL,
    SALARY_NOTE,
    Coverage,
    FxStatus,
    coverage_of,
    read_fx,
    stamp,
)
from etl.aggregate.premium import MIN_TOTAL_WITH, TOP_N, SkillPremium, skill_premiums
from etl.aggregate.series import DayPoint, timeseries
from etl.aggregate.snapshot import SnapshotPayload, build_snapshot
from etl.clock import SystemClock
from etl.publish import eval_badge, jobs_badge, write_json

__all__ = [
    "ATTRIBUTION",
    "BOARD_URL",
    "MIN_STRATUM",
    "MIN_TOTAL_WITH",
    "REPLICATES",
    "SALARY_NOTE",
    "TOP_N",
    "Coverage",
    "DayPoint",
    "FxStatus",
    "LabelIndex",
    "SkillPremium",
    "SnapshotPayload",
    "aggregate",
    "bootstrap_interval",
    "build_snapshot",
    "coverage_of",
    "labels_for",
    "open_dataset",
    "read_fx",
    "skill_premiums",
    "stamp",
    "timeseries",
    "weighted_premium",
    "eval_badge",
    "jobs_badge",
]

# Kept for the callers and suites written against the flat module.
_con = open_dataset


def skill_premium(con, latest_date, rng=None):
    """The published shape of :func:`skill_premiums`."""
    return [row.as_dict() for row in skill_premiums(con, latest_date, rng)]


def _top_companies(con, latest_date) -> list[dict]:
    rows = con.execute(
        "SELECT company, source, count(*) n FROM snap WHERE snapshot_date=? "
        "GROUP BY 1,2 ORDER BY n DESC, company LIMIT 10",
        [latest_date],
    ).fetchall()
    return [
        {"company": company, "n": int(n), "url": BOARD_URL[source].format(slug=company)}
        for company, source, n in rows
    ]


def _last_run(data_dir) -> dict:
    path = Path(data_dir) / "cache" / "last_run.json"
    return json.loads(path.read_text()) if path.exists() else {}


def aggregate(data_dir, site_data_dir, clock=None):
    """Build latest.json, timeseries.json, meta.json and badge.json."""
    now = (clock or SystemClock()).now()
    con = open_dataset(data_dir)
    try:
        latest_date = con.execute("SELECT max(snapshot_date) FROM snap").fetchone()[0]
        payload = build_snapshot(con, latest_date)
        write_json(site_data_dir, "latest.json", payload.as_dict())
        write_json(
            site_data_dir, "timeseries.json", [point.as_dict() for point in timeseries(con)]
        )

        with_salary, total = con.execute(
            "SELECT count(*) FILTER (has_salary), count(*) FROM snap WHERE snapshot_date=?",
            [latest_date],
        ).fetchone()
        processed = con.execute(
            "SELECT count(DISTINCT job_uid) FROM sk WHERE job_uid IN "
            "(SELECT job_uid FROM snap WHERE snapshot_date=?)",
            [latest_date],
        ).fetchone()[0]
        days = con.execute("SELECT count(DISTINCT snapshot_date) FROM snap").fetchone()[0]
        companies = con.execute(
            "SELECT count(DISTINCT company) FROM snap WHERE snapshot_date=?", [latest_date]
        ).fetchone()[0]
        by_source = dict(
            con.execute(
                "SELECT source, count(DISTINCT company) FROM snap WHERE snapshot_date=? GROUP BY 1",
                [latest_date],
            ).fetchall()
        )

        write_json(
            site_data_dir,
            "meta.json",
            {
                "updated_at": stamp(now),
                "days_collected": int(days),
                "companies_tracked": int(companies),
                "sources": by_source,
                "fx": read_fx(data_dir, now).as_dict(),
                "salary_note": SALARY_NOTE,
                "attribution": ATTRIBUTION,
                "skill_premium": skill_premium(con, latest_date),
                "top_companies": _top_companies(con, latest_date),
                "coverage": coverage_of(with_salary, processed, total, _last_run(data_dir)).as_dict(),
            },
        )
        write_json(site_data_dir, "badge.json", jobs_badge(payload.size).as_dict())
        print(f"aggregated: {payload.size} active rows @ {latest_date} -> {site_data_dir}/")
        return payload.size
    finally:
        con.close()
