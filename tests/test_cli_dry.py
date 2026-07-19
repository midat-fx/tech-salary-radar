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


def test_rerun_same_day_idempotent(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    seed = [{"source": "lever", "slug": "matchgroup", "name": "matchgroup"}]
    run(client, seed, str(tmp_path), "2026-08-20", pause=0)
    n1 = _count(tmp_path, "snapshots")
    run(client, seed, str(tmp_path), "2026-08-20", pause=0)
    assert _count(tmp_path, "snapshots") == n1   # partition overwritten, not appended
