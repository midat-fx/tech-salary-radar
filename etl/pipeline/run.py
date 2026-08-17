"""The daily run itself, as one function over a context.

Lifted out of ``etl/cli.py`` so the command-line layer parses arguments and
nothing else. The move is not cosmetic: the run is the only place where the
layers meet, so it is where an ordering mistake between them can happen, and it
was previously reachable only by constructing an argparse namespace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from etl.dedupe import DedupeReport, deduplicate
from etl.fx import fetch_rates
from etl.guards import Verdict, check_freshness, check_plausibility, check_volume
from etl.normalize import normalize_all
from etl.pipeline.context import RunContext
from etl.pipeline.stages import by_source
from etl.publish import write_partition
from etl.report import RunReport, collect
from etl.roles import passes_role_filter

__all__ = ["RunOutcome", "GuardRefused", "execute"]


class GuardRefused(RuntimeError):
    """A guard refused the day. Nothing was written.

    An exception rather than a return value because the caller is a cron job,
    and a non-zero exit is the only thing a cron job reliably notices.
    """

    def __init__(self, verdict: Verdict) -> None:
        super().__init__("; ".join(str(finding) for finding in verdict.refusals))
        self.verdict = verdict


@dataclass
class RunOutcome:
    """Everything a run produced, for the caller to print or assert on."""

    report: RunReport
    snapshot_rows: int
    new_rows: int
    skill_rows: int
    dedupe: DedupeReport
    verdict: Verdict

    def text(self) -> str:
        return self.report.text()


def _extract_skills(ctx: RunContext, jobs, snap):
    """Label what the budget allows. Returns (rows, stats) or ([], None)."""
    from etl.skills import extract_for_jobs, read_cache_state

    priority = {
        row["job_uid"]: (bool(row["has_salary"]), str(row["published_at"] or "")) for row in snap
    }
    technical = [job for job in jobs if passes_role_filter(job.get("title"), job.get("department"))]
    cache = read_cache_state(ctx.data_dir)
    return extract_for_jobs(
        technical,
        cache.current,
        priority=priority,
        stale_uids=cache.stale,
        log=ctx.say,
        clock=ctx.clock,
        sleeper=ctx.sleeper,
        **({"limit": ctx.llm_limit} if ctx.llm_limit is not None else {}),
    )


def execute(ctx: RunContext, client, seed, existing_uids) -> RunOutcome:
    """Fetch, normalise, de-duplicate, judge, and only then write."""
    from etl import salary as salary_mod
    from etl.fetch import iter_jobs

    salary_mod.reset_stats()

    jobs = list(
        iter_jobs(
            client,
            seed,
            log=ctx.say,
            sleeper=ctx.sleeper,
            **({} if ctx.pause is None else {"pause": ctx.pause}),
        )
    )
    rates = fetch_rates(client, ctx.data_dir, ctx.clock)

    result = normalize_all(jobs, rates, ctx.day, existing_uids)
    snap, new, stats = result["snapshot_rows"], result["new_rows"], result["stats"]

    snap, dedupe_report = deduplicate(snap)
    kept = {row["job_uid"] for row in snap}
    new = [row for row in new if row["job_uid"] in kept]

    verdict = check_volume(ctx.data_dir, ctx.day, by_source(snap))
    verdict.merge(check_plausibility(snap))
    verdict.merge(check_freshness(snap, ctx.day, rates.day, ctx.clock.now()))
    if not verdict.ok:
        raise GuardRefused(verdict)
    for warning in verdict.warnings:
        ctx.say(str(warning))

    write_partition(snap, ctx.data_dir, "snapshots", ctx.day, log=ctx.say)
    write_partition(new, ctx.data_dir, "jobs", ctx.day, log=ctx.say)

    skill_rows, llm_stats = 0, None
    if not ctx.skip_llm:
        rows, llm_stats = _extract_skills(ctx, jobs, snap)
        if rows:
            write_partition(rows, ctx.data_dir, "skills", ctx.day, append=True, log=ctx.say)
        skill_rows = len(rows)

    report = collect(
        day=ctx.day,
        seed_size=len(seed),
        raw_jobs=len(jobs),
        snapshot_rows=len(snap),
        new_rows=len(new),
        with_salary=sum(1 for row in snap if row["has_salary"]),
        filtered_non_tech=stats.get("filtered_non_tech", 0),
        skill_rows=skill_rows,
        dedupe=dedupe_report,
        guards=verdict,
        pay_stats=dict(salary_mod.STATS),
        llm_stats=llm_stats,
    )
    cache = ctx.data_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "last_run.json").write_text(json.dumps({"date": ctx.day, **report.as_dict()}))

    return RunOutcome(
        report=report,
        snapshot_rows=len(snap),
        new_rows=len(new),
        skill_rows=skill_rows,
        dedupe=dedupe_report,
        verdict=verdict,
    )
