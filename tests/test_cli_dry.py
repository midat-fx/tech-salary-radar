"""Stage-2 acceptance: run() on MockTransport fixtures writes snapshots/jobs partitions to tmp."""

import json
from pathlib import Path

import duckdb
import httpx

from etl.cli import run

FIX = Path(__file__).parent / "fixtures"
BODY = {"greenhouse": FIX.joinpath("greenhouse.json").read_text(),
        "lever": FIX.joinpath("lever.json").read_text(),
        "ashby": FIX.joinpath("ashby.json").read_text()}


def _handler(request):
    host = request.url.host
    if "er-api" in host:
        return httpx.Response(200, text=json.dumps(
            {"result": "success", "rates": {"USD": 1, "EUR": 0.92, "GBP": 0.79}}))
    for name, body in BODY.items():
        if name in host:
            return httpx.Response(200, text=body)
    return httpx.Response(404)


def _count(data_dir, table):
    glob = f"{data_dir}/{table}/*/part.parquet"
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{glob}')").fetchone()[0]


def test_run_writes_partitions(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    seed = [{"source": "greenhouse", "slug": "gitlab", "name": "gitlab"},
            {"source": "lever", "slug": "matchgroup", "name": "matchgroup"},
            {"source": "ashby", "slug": "linear", "name": "linear"}]
    summary = run(client, seed, str(tmp_path), "2026-08-20", pause=0)

    assert (tmp_path / "snapshots" / "dt=2026-08-20" / "part.parquet").exists()
    assert (tmp_path / "jobs" / "dt=2026-08-20" / "part.parquet").exists()
    assert _count(tmp_path, "snapshots") >= 1
    # lever matchgroup fixture carries a USD salaryRange -> at least one salary-bearing row
    with_sal = duckdb.sql(
        f"SELECT count(*) FROM read_parquet('{tmp_path}/snapshots/*/part.parquet') "
        "WHERE has_salary").fetchone()[0]
    assert with_sal >= 1
    assert summary["snapshot_rows"] == _count(tmp_path, "snapshots")


def test_volume_guard_blocks_collapsed_source(tmp_path):
    """A source collapsing to 30% of its median must abort BEFORE any partition is written —
    otherwise the append-only history records a fake market crash forever."""
    import pytest

    from etl.cli import VolumeGuardError, volume_guard
    from etl.normalize import write_partition
    for day in ("2026-08-17", "2026-08-18", "2026-08-19"):
        rows = [{"job_uid": f"greenhouse:c:{day}-{i}", "snapshot_date": day, "source": "greenhouse",
                 "company": "c", "region": "us", "is_remote": False, "seniority": "senior",
                 "is_management": False, "salary_min_usd": None, "salary_max_usd": None,
                 "salary_mid_usd": None, "has_salary": False, "employment_type": None,
                 "published_at": None} for i in range(100)]
        write_partition(rows, tmp_path, "snapshots", day)

    assert volume_guard(str(tmp_path), "2026-08-20", {"greenhouse": 95}) == []      # healthy day
    problems = volume_guard(str(tmp_path), "2026-08-20", {"greenhouse": 30})        # collapsed
    assert problems and "greenhouse" in problems[0]

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    seed = [{"source": "lever", "slug": "matchgroup", "name": "matchgroup"}]
    with pytest.raises(VolumeGuardError):
        run(client, seed, str(tmp_path), "2026-08-20", pause=0)
    assert not (tmp_path / "snapshots" / "dt=2026-08-20").exists()   # nothing written


def test_volume_guard_silent_until_enough_history(tmp_path):
    from etl.cli import volume_guard
    assert volume_guard(str(tmp_path), "2026-08-20", {"greenhouse": 1}) == []


def test_rerun_same_day_idempotent(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    seed = [{"source": "lever", "slug": "matchgroup", "name": "matchgroup"}]
    run(client, seed, str(tmp_path), "2026-08-20", pause=0)
    snap1, jobs1 = _count(tmp_path, "snapshots"), _count(tmp_path, "jobs")
    run(client, seed, str(tmp_path), "2026-08-20", pause=0)
    # partitions overwritten, not appended; the jobs partition must NOT be wiped on re-run
    # (anti-join excludes the day's own partition; see the empty-partition bug)
    assert _count(tmp_path, "snapshots") == snap1
    assert _count(tmp_path, "jobs") == jobs1 > 0
