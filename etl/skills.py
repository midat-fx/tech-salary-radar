"""Skill extraction via Gemini structured output, cached (PLAN.md §6, stage 5).

ATS boards have no free key_skills ground truth, so skills come only from the LLM (source='llm').
Descriptions are only available during a fetch run, so extraction runs there (not from parquet).
"""

import json
import os
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


def extract_for_jobs(jobs, processed_uids, limit=LLM_DAILY_JOB_LIMIT, call=_gemini_call,
                     pause=LLM_PAUSE_SEC, log=print):
    """Extract skills for fetched jobs whose uid is not yet cached (freshest first).

    Returns skill rows: one per (job_uid, skill); a processed job with no skills -> one NULL row.
    """
    import time

    from etl.normalize import job_uid
    pending, seen = [], set()
    for j in jobs:
        uid = job_uid(j["source"], j["company"], j["job_id"])
        if uid in processed_uids or uid in seen:
            continue
        seen.add(uid)
        pending.append((uid, j))
    pending = pending[:limit]
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i in range(0, len(pending), LLM_BATCH_SIZE):
        chunk = pending[i:i + LLM_BATCH_SIZE]
        batch = [{"id": n, "title": j["title"], "text": j.get("description", "")}
                 for n, (_, j) in enumerate(chunk)]
        try:
            result = extract_llm(batch, call=call)
        except Exception as e:
            log(f"llm batch failed, skipping (will retry next run): {e}")
            break
        for n, (uid, _) in enumerate(chunk):
            skills = result.get(n, [])
            if skills:
                rows.extend(_row(uid, s, now) for s in skills)
            else:
                rows.append(_row(uid, None, now))
        if pause and i + LLM_BATCH_SIZE < len(pending):
            time.sleep(pause)
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
