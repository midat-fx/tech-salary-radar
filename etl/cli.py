"""Command-line entry point: python -m etl.cli run|backfill|aggregate."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from etl import aggregate as agg
from etl.config import TZ
from etl.fetch import iter_jobs, load_seed, make_client
from etl.fx import fetch_rates
from etl.normalize import normalize_all, write_partition


def today_str():
    return datetime.now(ZoneInfo(TZ)).date().isoformat()


def existing_job_uids(data_dir):
    """DISTINCT job_uid across all data/jobs/* partitions (empty set if none yet)."""
    glob = Path(data_dir) / "jobs"
    if not any(glob.rglob("*.parquet")):
        return set()
    import duckdb
    q = f"SELECT DISTINCT job_uid FROM read_parquet('{glob}/*/part.parquet')"
    return {r[0] for r in duckdb.sql(q).fetchall()}


def run(client, seed, data_dir, dt, pause=None, log=print, skip_llm=True, llm_limit=None):
    """Testable core: fetch -> fx -> normalize -> write partitions (+ optional skills). Returns summary."""
    kwargs = {"log": log} if pause is None else {"log": log, "pause": pause}
    jobs = list(iter_jobs(client, seed, **kwargs))
    rates = fetch_rates(client, data_dir)
    result = normalize_all(jobs, rates, dt, existing_job_uids(data_dir))
    snap, new, stats = result["snapshot_rows"], result["new_rows"], result["stats"]
    write_partition(snap, data_dir, "snapshots", dt)
    write_partition(new, data_dir, "jobs", dt)

    skill_rows = 0
    if not skip_llm:
        from etl.normalize import passes_role_filter
        from etl.skills import extract_for_jobs, processed_uids
        tech = [j for j in jobs if passes_role_filter(j.get("title"), j.get("department"))]
        limit = llm_limit if llm_limit is not None else None
        rows = extract_for_jobs(tech, processed_uids(data_dir),
                                **({"limit": limit} if limit is not None else {}), log=log)
        if rows:
            write_partition(rows, data_dir, "skills", dt)
        skill_rows = len(rows)

    summary = {"boards": len(seed), "raw_jobs": len(jobs), "snapshot_rows": len(snap),
               "new_rows": len(new), "with_salary": sum(1 for r in snap if r["has_salary"]),
               "skill_rows": skill_rows, "by_source": dict(Counter(r["source"] for r in snap)), **stats}
    cache = Path(data_dir) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "last_run.json").write_text(json.dumps({"date": dt, **stats}))
    return summary


def cmd_run(args):
    """Daily increment: fetch -> normalize -> fx -> parquet partitions (skills = stage 5)."""
    dt = today_str()
    s = run(make_client(), load_seed(), args.data_dir, dt,
            skip_llm=args.skip_llm, llm_limit=args.llm_limit)
    print(f"\n=== run {dt} ===")
    print(f"boards: {s['boards']} | raw jobs fetched: {s['raw_jobs']}")
    print(f"snapshot rows: {s['snapshot_rows']} by source {s['by_source']}")
    print(f"with salary: {s['with_salary']} | new job_uids: {s['new_rows']}")
    print(f"filtered non-tech: {s['filtered_non_tech']} | dropped OOB salary: {s['dropped_oob']}")
    if not args.skip_llm:
        print("(skills extraction: stage 5 — run with GEMINI_API_KEY)")


def cmd_backfill(args):
    """One-off: rebuild data/jobs/* keyed by each open job's publish date (PLAN.md stage 4)."""
    import shutil

    from etl.normalize import backfill_job_rows
    dt = today_str()
    client = make_client()
    jobs = list(iter_jobs(client, load_seed(), log=print))
    rates = fetch_rates(client, args.data_dir)
    jobs_dir = Path(args.data_dir) / "jobs"
    if jobs_dir.exists():
        shutil.rmtree(jobs_dir)          # Шаг 0: retro rebuild of the whole pool by publish date
    by_date = backfill_job_rows(jobs, rates, dt)
    for fs, rows in sorted(by_date.items()):
        write_partition(rows, args.data_dir, "jobs", fs)
    total = sum(len(v) for v in by_date.values())
    print(f"backfill: {total} jobs across {len(by_date)} publish dates "
          f"({min(by_date)}..{max(by_date)})")


def cmd_aggregate(args):
    """Rebuild site/data/*.json from the committed parquet history."""
    agg.aggregate(args.data_dir, args.site_data_dir)


def build_parser():
    parser = argparse.ArgumentParser(prog="etl.cli")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--site-data-dir", default="site/data")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="daily increment")
    p_run.add_argument("--skip-llm", action="store_true")
    p_run.add_argument("--llm-limit", type=int, default=None)
    p_run.set_defaults(func=cmd_run)

    p_backfill = sub.add_parser("backfill", help="one-off retro backfill")
    p_backfill.set_defaults(func=cmd_backfill)

    p_aggregate = sub.add_parser("aggregate", help="rebuild site/data JSON")
    p_aggregate.set_defaults(func=cmd_aggregate)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
