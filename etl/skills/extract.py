"""Send batches to the model and turn its answers into storable rows.

Three things here are load-bearing and none of them is the model call.

**A dropped id stays queued.** When the model omits a posting from its reply,
writing a null row for it would say "labelled, found nothing" — permanently,
into an append-only cache. It is left unwritten and tried again tomorrow.

**Quota stops the day, failures stop after three.** Quota exhaustion is not
transient: retrying spends the next day's budget on error responses. Three
consecutive failures of any other kind mean something is wrong that a fourth
attempt will not fix.

**The pause is injected.** Proving the batching and the stopping rules used to
require eight real seconds per batch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from etl.clock import Clock, Sleeper, SystemClock, SystemSleeper, iso_second
from etl.config import LLM_BATCH_SIZE, LLM_DAILY_JOB_LIMIT, LLM_PAUSE_SEC, LLM_TEXT_TRIM
from etl.schema.job import job_uid
from etl.skills.catalog import canonicalize
from etl.skills.prompt import PROMPT_VERSION, build_payload
from etl.skills.queue import Candidate, prioritise

__all__ = ["ExtractionStats", "extract_batch", "extract_for_jobs", "QUOTA_PATTERN", "MAX_FAILURES"]

#: How the free tier says "you are done for today", in every wording it uses.
QUOTA_PATTERN = re.compile(r"resource_exhausted|quota|429", re.I)

#: Consecutive non-quota failures before giving up on the run.
MAX_FAILURES = 3


@dataclass
class ExtractionStats:
    """What the run did, in the terms that explain a coverage number."""

    queue_depth: int = 0
    extracted: int = 0
    empty_results: int = 0
    missing_ids: int = 0
    failed_batches: int = 0
    companies: int = 0
    stopped_on_quota: bool = False

    def as_dict(self) -> dict[str, int]:
        return {
            "queue_depth": self.queue_depth,
            "extracted": self.extracted,
            "empty_results": self.empty_results,
            "missing_ids": self.missing_ids,
            "failed_batches": self.failed_batches,
            "companies": self.companies,
            "stopped_on_quota": int(self.stopped_on_quota),
        }

    def describe(self) -> str:
        return (
            f"skills: {self.extracted}/{self.queue_depth} labelled across {self.companies} companies"
            f" ({self.empty_results} empty, {self.missing_ids} dropped by the model,"
            f" {self.failed_batches} failed batches"
            f"{', quota reached' if self.stopped_on_quota else ''})"
        )


def extract_batch(batch: list[dict], call, text_limit: int = LLM_TEXT_TRIM) -> dict[int, list[str]]:
    """One request. Returns id -> canonical skills; ids the model dropped are absent.

    Names outside the catalog are discarded rather than stored: the response
    schema pins the enum, so anything else is the model ignoring it, and a name
    with no column is a row nothing can ever join against.
    """
    data = call(build_payload(batch, text_limit))
    labelled: dict[int, list[str]] = {}
    for item in data.get("items", []):
        canonical = {canonicalize(name) for name in item.get("skills", [])}
        labelled[item["id"]] = sorted(name for name in canonical if name)
    return labelled


def _row(uid: str, skill: str | None, stamp: str) -> dict:
    return {
        "job_uid": uid,
        "skill": skill,
        "source": "llm",
        "prompt_version": PROMPT_VERSION,
        "extracted_at": stamp,
    }


@dataclass
class _Run:
    rows: list[dict] = field(default_factory=list)
    stats: ExtractionStats = field(default_factory=ExtractionStats)
    consecutive_failures: int = 0


def build_queue(
    jobs: list[dict],
    processed: set[str] | frozenset[str],
    priority: dict[str, tuple[bool, str]] | None = None,
    stale: frozenset[str] = frozenset(),
) -> list[Candidate]:
    """Everything worth labelling, in the order it should be labelled.

    A posting with no description is skipped without being counted as queued:
    there is nothing to read, and caching a null row for it would claim the
    model looked.
    """
    priority = priority or {}
    seen: set[str] = set()
    queue: list[Candidate] = []
    for job in jobs:
        uid = job_uid(job["source"], job["company"], job["job_id"])
        if uid in processed or uid in seen:
            continue
        if not (job.get("description") or "").strip():
            continue
        seen.add(uid)
        has_salary, published = priority.get(uid, (False, ""))
        queue.append(Candidate(uid, job, has_salary, published, uid in stale))
    return queue


def extract_for_jobs(
    jobs: list[dict],
    processed_uids: set[str] | frozenset[str],
    limit: int = LLM_DAILY_JOB_LIMIT,
    call=None,
    pause: float = LLM_PAUSE_SEC,
    log=print,
    priority: dict[str, tuple[bool, str]] | None = None,
    stale_uids: frozenset[str] = frozenset(),
    clock: Clock | None = None,
    sleeper: Sleeper | None = None,
    batch_size: int = LLM_BATCH_SIZE,
) -> tuple[list[dict], ExtractionStats]:
    """Label what the budget allows, and report what happened to the rest."""
    clock = clock or SystemClock()
    sleeper = sleeper or SystemSleeper()
    if call is None:
        from etl.skills.client import gemini_call

        call = gemini_call

    queue = build_queue(jobs, processed_uids, priority, stale_uids)
    run = _Run()
    run.stats.queue_depth = len(queue)
    selected = prioritise(queue, limit)
    stamp = iso_second(clock.now())

    for start in range(0, len(selected), batch_size):
        chunk = selected[start : start + batch_size]
        batch = [
            {"id": index, "title": c.job.get("title", ""), "text": c.job.get("description", "")}
            for index, c in enumerate(chunk)
        ]
        try:
            answered = extract_batch(batch, call)
            run.consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001 - the reason decides what to do
            run.stats.failed_batches += 1
            run.consecutive_failures += 1
            if QUOTA_PATTERN.search(str(exc)):
                run.stats.stopped_on_quota = True
                log(f"llm quota reached, stopping for today: {exc}")
                break
            log(f"llm batch failed ({run.consecutive_failures}/{MAX_FAILURES}), continuing: {exc}")
            if run.consecutive_failures >= MAX_FAILURES:
                log(f"{MAX_FAILURES} consecutive llm failures — stopping")
                break
            continue

        for index, candidate in enumerate(chunk):
            skills = answered.get(index)
            if skills is None:
                run.stats.missing_ids += 1
                continue
            if skills:
                run.rows.extend(_row(candidate.uid, name, stamp) for name in skills)
            else:
                run.stats.empty_results += 1
                run.rows.append(_row(candidate.uid, None, stamp))
            run.stats.extracted += 1

        if pause and start + batch_size < len(selected):
            sleeper.sleep(pause)

    run.stats.companies = len({c.job.get("company", "") for c in selected})
    return run.rows, run.stats
