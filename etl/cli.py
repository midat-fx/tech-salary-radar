"""Command-line entry point: python -m etl.cli run|backfill|aggregate."""

import argparse
from pathlib import Path

from etl import aggregate as agg
from etl.clock import SystemClock
from etl.config import TZ
from etl.pipeline import GuardRefused, build_context, execute
from etl.fetch import iter_jobs, load_seed, make_client
from etl.fx import fetch_rates
from etl.normalize import write_partition


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
    """Testable core, kept as a function for the suites written against it.

    The orchestration itself moved to :mod:`etl.pipeline.run`; this is the
    argument shape the existing callers use.
    """
    ctx = build_context(
        data_dir=data_dir, day=dt, log=log, skip_llm=skip_llm, llm_limit=llm_limit, pause=pause
    )
    try:
        outcome = execute(ctx, client, seed, existing_job_uids(data_dir, exclude_dt=dt))
    except GuardRefused as refused:
        raise VolumeGuardError(str(refused)) from refused
    return {
        "boards": len(seed),
        "snapshot_rows": outcome.snapshot_rows,
        "new_rows": outcome.new_rows,
        "skill_rows": outcome.skill_rows,
        "report": outcome.report,
        "dedupe": outcome.dedupe,
        **outcome.report.as_dict(),
    }


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
