"""Skill extraction via Gemini structured output, cached (PLAN.md §6, stage 5).

ATS boards have no free key_skills ground truth, so skills come only from the LLM (source='llm').
Descriptions are only available during a fetch run, so extraction runs there (not from parquet).
"""

import json
import os
import re
from datetime import datetime, timezone

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from etl.config import (
    LLM_BATCH_SIZE,
    LLM_DAILY_JOB_LIMIT,
    LLM_MODEL,
    LLM_PAUSE_SEC,
    LLM_TEXT_TRIM,
    PROMPT_VERSION,
)
from etl.skills_catalog import CANONICAL, canonicalize

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"items": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "INTEGER"},
                       "skills": {"type": "ARRAY", "items": {"type": "STRING", "enum": CANONICAL}}},
        "required": ["id", "skills"]}}},
    "required": ["items"],
}

PROMPT = """You label job postings with technology skills.
Input: a JSON array of postings, each {"id": int, "title": str, "text": str}, in Russian or English.
For EVERY posting return the skills from the allowed list that are EXPLICITLY mentioned in its title or text.
Rules:
- Use only skills from the allowed list, with exact canonical spelling.
- Explicit mentions only ("питон" -> Python, "верстка" -> HTML/CSS). Do not infer skills from job title level, company type, or typical stacks.
- Single allowed inference: a framework implies its language (Django/FastAPI/Flask -> also Python).
- If nothing matches, return an empty skills array for that id.
- Return every input id exactly once."""


class _Transient(Exception):
    pass


def _gemini_call(batch_input):
    """Real Gemini call: returns parsed {"items": [...]}."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    content = PROMPT + "\n\nInput:\n" + json.dumps(batch_input, ensure_ascii=False)
    try:
        resp = client.models.generate_content(
            model=LLM_MODEL, contents=content,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=RESPONSE_SCHEMA,
                temperature=0, max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_budget=0)))
    except Exception as e:  # 429/503 etc. -> retry
        raise _Transient(str(e)) from e
    return json.loads(resp.text)


@retry(retry=retry_if_exception_type(_Transient), wait=wait_fixed(30),
       stop=stop_after_attempt(3), reraise=True)
def extract_llm(batch, call=_gemini_call):
    """Label a batch of postings [{id,title,text}] -> {id: [canonical skills]}.

    `call` is injectable for testing; defaults to the real Gemini call.
    """
    payload = [{"id": b["id"], "title": b["title"][:200],
                "text": (b["text"] or "")[:LLM_TEXT_TRIM]} for b in batch]
    data = call(payload)
    out = {}
    for item in data.get("items", []):
        skills = {canonicalize(s) for s in item.get("skills", [])}
        out[item["id"]] = sorted(s for s in skills if s)
    return out


STATS = {"empty_results": 0, "missing_ids": 0, "failed_batches": 0,
         "queue_depth": 0, "extracted": 0, "companies": 0}


def reset_stats():
    for k in STATS:
        STATS[k] = 0


_QUOTA = re.compile(r"resource_exhausted|quota|429", re.I)


def _prioritise(pending, priority):
    """Salary-bearing jobs first (they are the only ones the flagship metric can use), newest first,
    then round-robin across sources so one alphabetically-early ATS cannot monopolise the budget."""
    def key(item):
        uid, _ = item
        has_salary, published = priority.get(uid, (False, ""))
        return (0 if has_salary else 1, _neg_date(published))
    ordered = sorted(pending, key=key)
    buckets = {}
    for uid, job in ordered:
        buckets.setdefault(job["source"], []).append((uid, job))
    out = []
    while any(buckets.values()):
        for src in list(buckets):
            if buckets[src]:
                out.append(buckets[src].pop(0))
    return out


def _neg_date(published):
    """Sort key that puts the newest ISO timestamp first."""
    return tuple(-ord(c) for c in (published or ""))


def extract_for_jobs(jobs, processed_uids, limit=LLM_DAILY_JOB_LIMIT, call=_gemini_call,
                     pause=LLM_PAUSE_SEC, log=print, priority=None):
    """Extract skills for fetched jobs whose uid is not yet cached.

    Order: salary-bearing first, then newest, round-robin across sources (`priority` maps
    uid -> (has_salary, published_at)). Returns skill rows: one per (job_uid, skill); a job the
    model processed with no skills -> one NULL row. Jobs the model silently dropped are NOT
    written (a NULL row would poison the append-only cache forever) and stay queued.
    """
    import time

    from etl.normalize import job_uid
    pending, seen = [], set()
    for j in jobs:
        uid = job_uid(j["source"], j["company"], j["job_id"])
        if uid in processed_uids or uid in seen:
            continue
        if not (j.get("description") or "").strip():
            continue                       # nothing to label; don't burn a slot or cache a NULL
        seen.add(uid)
        pending.append((uid, j))
    STATS["queue_depth"] = len(pending)
    pending = _prioritise(pending, priority or {})[:limit]
    now = datetime.now(timezone.utc).isoformat()
    rows, consecutive_failures = [], 0
    for i in range(0, len(pending), LLM_BATCH_SIZE):
        chunk = pending[i:i + LLM_BATCH_SIZE]
        batch = [{"id": n, "title": j["title"], "text": j.get("description", "")}
                 for n, (_, j) in enumerate(chunk)]
        try:
            result = extract_llm(batch, call=call)
            consecutive_failures = 0
        except Exception as e:
            STATS["failed_batches"] += 1
            consecutive_failures += 1
            if _QUOTA.search(str(e)):
                log(f"llm quota reached, stopping for today: {e}")
                break
            log(f"llm batch failed ({consecutive_failures}/3), continuing: {e}")
            if consecutive_failures >= 3:
                log("three consecutive llm failures — stopping")
                break
            continue
        for n, (uid, _) in enumerate(chunk):
            skills = result.get(n)
            if skills is None:             # model omitted this id — leave it queued
                STATS["missing_ids"] += 1
                continue
            if skills:
                rows.extend(_row(uid, s, now) for s in skills)
            else:
                STATS["empty_results"] += 1
                rows.append(_row(uid, None, now))
            STATS["extracted"] += 1
        if pause and i + LLM_BATCH_SIZE < len(pending):
            time.sleep(pause)
    STATS["companies"] = len({uid.split(":")[1] for uid, _ in pending})
    return rows


def _row(uid, skill, now):
    return {"job_uid": uid, "skill": skill, "source": "llm",
            "prompt_version": PROMPT_VERSION, "extracted_at": now}


def processed_uids(data_dir):
    """DISTINCT job_uid already in the skills cache (empty set if none)."""
    from pathlib import Path
    glob = Path(data_dir) / "skills"
    if not any(glob.rglob("*.parquet")):
        return set()
    import duckdb
    return {r[0] for r in duckdb.sql(
        f"SELECT DISTINCT job_uid FROM read_parquet('{glob}/*/part.parquet')").fetchall()}
