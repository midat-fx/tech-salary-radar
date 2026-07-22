"""Command-line entry point: python -m etl.cli run|backfill|aggregate."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from etl import aggregate as agg
from etl.config import TZ
from etl.fetch import iter_jobs, load_seed, make_client
from etl import salary as salary_mod
from etl.fx import fetch_rates
from etl.normalize import normalize_all, write_partition


def today_str():
    return datetime.now(ZoneInfo(TZ)).date().isoformat()


def existing_job_uids(data_dir, exclude_dt=None):
    """DISTINCT job_uid across data/jobs/* partitions, excluding the given dt (so a same-day
    re-run reproduces its own 'new' set instead of wiping it). Empty set if none."""
    root = Path(data_dir) / "jobs"
    parts = [p for p in root.glob("dt=*/part.parquet") if p.parent.name != f"dt={exclude_dt}"]
    if not parts:
        return set()
    import duckdb
    files = ",".join(f"'{p}'" for p in parts)
    return {r[0] for r in duckdb.sql(f"SELECT DISTINCT job_uid FROM read_parquet([{files}])").fetchall()}


class VolumeGuardError(RuntimeError):
    """A source collapsed vs its recent history — refuse to write a poisoned day."""


MIN_HISTORY_DAYS = 3
SOURCE_FLOOR = 0.5      # a source must keep >=50% of its 7-day median
TOTAL_FLOOR = 0.6       # ...and the day must keep >=60% of the expected total


def volume_guard(data_dir, dt, by_source):
    """Compare today's per-source row counts with the 7-day medians; return a list of problems.

    A full Greenhouse outage (66% of the dataset) would otherwise be committed as a real market
    crash into the append-only history, and timeseries would never recover from it.
    """
    root = Path(data_dir) / "snapshots"
    parts = [p for p in root.glob("dt=*/part.parquet") if p.parent.name != f"dt={dt}"]
    if len(parts) < MIN_HISTORY_DAYS:
        return []                     # not enough history to judge; don't block the launch week
    import duckdb
    files = ",".join(f"'{p}'" for p in parts)
    rows = duckdb.sql(f"SELECT source, snapshot_date, count(*) FROM read_parquet([{files}]) "
                      "GROUP BY 1,2 ORDER BY 2 DESC").fetchall()
    hist = {}
    for src, _d, n in rows:
        hist.setdefault(src, []).append(n)
    problems, expected_total = [], 0
    for src, counts in hist.items():
        med = median(counts[:7])
        expected_total += med
        got = by_source.get(src, 0)
        if got < SOURCE_FLOOR * med:
            problems.append(f"{src}: {got} rows vs 7-day median {med:.0f}")
    got_total = sum(by_source.values())
    if expected_total and got_total < TOTAL_FLOOR * expected_total:
        problems.append(f"total: {got_total} rows vs expected ~{expected_total:.0f}")
    return problems


def run(client, seed, data_dir, dt, pause=None, log=print, skip_llm=True, llm_limit=None):
    """Testable core: fetch -> fx -> normalize -> write partitions (+ optional skills). Returns summary."""
    salary_mod.reset_stats()
    kwargs = {"log": log} if pause is None else {"log": log, "pause": pause}
    jobs = list(iter_jobs(client, seed, **kwargs))
    rates = fetch_rates(client, data_dir)
    result = normalize_all(jobs, rates, dt, existing_job_uids(data_dir, exclude_dt=dt))
    snap, new, stats = result["snapshot_rows"], result["new_rows"], result["stats"]
    by_source = dict(Counter(r["source"] for r in snap))
    problems = volume_guard(data_dir, dt, by_source)
    if problems:
        raise VolumeGuardError("; ".join(problems))
    write_partition(snap, data_dir, "snapshots", dt)
    write_partition(new, data_dir, "jobs", dt)

    skill_rows = 0
    llm_stats = {}
    if not skip_llm:
        from etl.normalize import passes_role_filter
        from etl.skills import STATS as LLM_STATS
        from etl.skills import extract_for_jobs, processed_uids
        from etl.skills import reset_stats as reset_llm_stats
        reset_llm_stats()
        # the flagship metric can only use salary-bearing jobs -> label those first
        priority = {r["job_uid"]: (bool(r["has_salary"]), str(r["published_at"] or "")) for r in snap}
        tech = [j for j in jobs if passes_role_filter(j.get("title"), j.get("department"))]
        limit = llm_limit if llm_limit is not None else None
        rows = extract_for_jobs(tech, processed_uids(data_dir), priority=priority,
                                **({"limit": limit} if limit is not None else {}), log=log)
        if rows:
            write_partition(rows, data_dir, "skills", dt)
        skill_rows = len(rows)
        llm_stats = {f"llm_{k}": v for k, v in LLM_STATS.items()}

    summary = {"boards": len(seed), "raw_jobs": len(jobs), "snapshot_rows": len(snap),
               "new_rows": len(new), "with_salary": sum(1 for r in snap if r["has_salary"]),
               "skill_rows": skill_rows, "by_source": by_source,
               **stats, **dict(salary_mod.STATS), **llm_stats}
    cache = Path(data_dir) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "last_run.json").write_text(json.dumps(
        {"date": dt, "by_source": by_source, **stats, **dict(salary_mod.STATS), **llm_stats}))
    return summary


def cmd_run(args):
    """Daily increment: fetch -> normalize -> fx -> parquet partitions (skills = stage 5)."""
    import sys
    dt = today_str()
    try:
        s = run(make_client(), load_seed(), args.data_dir, dt,
                skip_llm=args.skip_llm, llm_limit=args.llm_limit)
    except VolumeGuardError as e:
        print(f"VOLUME GUARD: refusing to write {dt} — {e}", file=sys.stderr)
        sys.exit(2)
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
