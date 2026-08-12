"""Command-line entry point: python -m etl.cli run|backfill|aggregate."""

import argparse
import json
from collections import Counter
from pathlib import Path

from etl import aggregate as agg
from etl.clock import SystemClock
from etl.config import TZ
from etl.dedupe import deduplicate
from etl.guards import check_plausibility, check_volume
from etl.report import collect
from etl.fetch import iter_jobs, load_seed, make_client
from etl import salary as salary_mod
from etl.fx import fetch_rates
from etl.normalize import normalize_all, write_partition


def today_str(clock=None):
    """The snapshot partition this run belongs to, in the project's reporting timezone."""
    return (clock or SystemClock()).today(TZ).isoformat()


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
    """A source collapsed against its recent history — refuse to write a poisoned day.

    Still an exception rather than a return value: the caller is a cron job, and
    a non-zero exit is the only thing a cron job reliably notices.
    """


def run(client, seed, data_dir, dt, pause=None, log=print, skip_llm=True, llm_limit=None):
    """Testable core: fetch -> fx -> normalize -> dedupe -> guards -> write. Returns a summary."""
    salary_mod.reset_stats()
    kwargs = {"log": log} if pause is None else {"log": log, "pause": pause}
    jobs = list(iter_jobs(client, seed, **kwargs))
    rates = fetch_rates(client, data_dir)
    result = normalize_all(jobs, rates, dt, existing_job_uids(data_dir, exclude_dt=dt))
    snap, new, stats = result["snapshot_rows"], result["new_rows"], result["stats"]

    # One job on two boards is one job: see ADR 0009. Done before the guards so
    # the volume comparison is like for like across days.
    snap, dedupe_report = deduplicate(snap)
    kept = {row["job_uid"] for row in snap}
    new = [row for row in new if row["job_uid"] in kept]

    by_source = dict(Counter(r["source"] for r in snap))
    verdict = check_volume(data_dir, dt, by_source)
    verdict.merge(check_plausibility(snap))
    if not verdict.ok:
        raise VolumeGuardError("; ".join(str(f) for f in verdict.refusals))
    for warning in verdict.warnings:
        log(str(warning))
    write_partition(snap, data_dir, "snapshots", dt, log=log)
    write_partition(new, data_dir, "jobs", dt, log=log)

    skill_rows = 0
    llm_stats, llm_stats_obj = {}, None
    if not skip_llm:
        from etl.normalize import passes_role_filter
        from etl.skills import extract_for_jobs, read_cache_state
        # the flagship metric can only use salary-bearing jobs -> label those first
        priority = {r["job_uid"]: (bool(r["has_salary"]), str(r["published_at"] or "")) for r in snap}
        tech = [j for j in jobs if passes_role_filter(j.get("title"), j.get("department"))]
        cache = read_cache_state(data_dir)
        rows, llm = extract_for_jobs(
            tech, cache.current, priority=priority, stale_uids=cache.stale, log=log,
            **({"limit": llm_limit} if llm_limit is not None else {}))
        if rows:
            write_partition(rows, data_dir, "skills", dt, append=True, log=log)
        skill_rows = len(rows)
        llm_stats_obj = llm
        llm_stats = {f"llm_{k}": v for k, v in llm.as_dict().items()}

    report = collect(
        day=dt,
        seed_size=len(seed),
        raw_jobs=len(jobs),
        snapshot_rows=len(snap),
        new_rows=len(new),
        with_salary=sum(1 for r in snap if r["has_salary"]),
        filtered_non_tech=stats.get("filtered_non_tech", 0),
        skill_rows=skill_rows,
        dedupe=dedupe_report,
        guards=verdict,
        pay_stats=dict(salary_mod.STATS),
        llm_stats=llm_stats_obj,
    )
    summary = {"boards": len(seed), "raw_jobs": len(jobs), "snapshot_rows": len(snap),
               "new_rows": len(new), "with_salary": sum(1 for r in snap if r["has_salary"]),
               "skill_rows": skill_rows, "by_source": by_source, "report": report,
               "dedupe": dedupe_report, **stats, **dict(salary_mod.STATS), **llm_stats}
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
    print()
    print(s["report"].text())


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
