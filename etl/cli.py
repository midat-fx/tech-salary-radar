"""Command-line entry point: python -m etl.cli run|backfill|aggregate."""

import argparse


def cmd_run(args):
    """Daily increment: fetch -> normalize -> fx -> skills -> parquet partitions."""
    raise NotImplementedError


def cmd_backfill(args):
    """One-off backfill of BACKFILL_DAYS of vacancies by published_at (PLAN.md stage 4)."""
    raise NotImplementedError


def cmd_aggregate(args):
    """Rebuild site/data/*.json from the committed parquet history."""
    raise NotImplementedError


def build_parser():
    parser = argparse.ArgumentParser(prog="etl.cli")
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
