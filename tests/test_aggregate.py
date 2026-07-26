"""skill_premium: only LLM-processed jobs form the pools; bootstrap CI is reported (PLAN.md §3.6)."""

from etl.aggregate import _con, skill_premium
from etl.normalize import write_partition

DT = "2026-08-20"


def _snap(uid, mid, seniority="senior", region="us"):
    return {"job_uid": uid, "snapshot_date": DT, "source": "ashby", "company": "c",
            "region": region, "is_remote": False, "seniority": seniority,
            "is_management": False, "salary_min_usd": mid, "salary_max_usd": mid,
            "salary_mid_usd": mid, "has_salary": True, "employment_type": "FullTime",
            "published_at": "2026-08-01T00:00:00+00:00"}


def _skill_row(uid, skill):
    return {"job_uid": uid, "skill": skill, "source": "llm",
            "prompt_version": "v1", "extracted_at": "2026-08-20T00:00:00+00:00"}


def _build(tmp_path, n_unprocessed, unprocessed_mid=500_000):
    """16 processed jobs WITH Python @200k, 10 processed WITHOUT @100k, N unprocessed @500k.

    16 (not 10) because a skill needs >=15 salary-bearing jobs overall to qualify (PLAN.md §3.6).
    """
    snaps, jobs, skills = [], [], []
    for i in range(16):
        uid = f"ashby:c:with{i}"
        snaps.append(_snap(uid, 200_000))
        skills.append(_skill_row(uid, "Python"))
    for i in range(10):
        uid = f"ashby:c:without{i}"
        snaps.append(_snap(uid, 100_000))
        skills.append(_skill_row(uid, None))      # processed, no skills found
    for i in range(n_unprocessed):
        uid = f"ashby:c:pending{i}"
        snaps.append(_snap(uid, unprocessed_mid))  # never sent to the LLM
    jobs = [{"job_uid": s["job_uid"], "first_seen": DT} for s in snaps]
    write_partition(snaps, tmp_path, "snapshots", DT)
    write_partition(jobs, tmp_path, "jobs", DT)
    write_partition(skills, tmp_path, "skills", DT)
    return _con(str(tmp_path))


def test_unprocessed_jobs_do_not_dilute_premium(tmp_path):
    """Pending jobs (no skills row) are not evidence of 'skill absent' — they must be excluded.

    With contamination their 500k salaries would dominate the without-pool and flip the ratio
    below 1.0, dropping Python from the results entirely.
    """
    con = _build(tmp_path, n_unprocessed=50)
    res = skill_premium(con, DT)
    con.close()
    py = next((r for r in res if r["skill"] == "Python"), None)
    assert py is not None, "Python vanished -> unprocessed jobs leaked into the without-pool"
    assert abs(py["premium_pct"] - 100.0) < 1e-6      # 200k vs 100k medians
    assert py["n"] == 16


def test_newest_prompt_version_wins(tmp_path):
    """A job labelled by two prompt generations must count only under the newest one, so a prompt
    upgrade rolls out per job instead of mixing v1 and v2 labels in one metric."""
    snaps = [_snap("ashby:c:1", 200_000)]
    write_partition(snaps, tmp_path, "snapshots", DT)
    write_partition([{"job_uid": "ashby:c:1", "first_seen": DT}], tmp_path, "jobs", DT)
    write_partition([
        {"job_uid": "ashby:c:1", "skill": "Python", "source": "llm",
         "prompt_version": "v1", "extracted_at": "2026-08-19T00:00:00+00:00"},
        {"job_uid": "ashby:c:1", "skill": "Go", "source": "llm",
         "prompt_version": "v2", "extracted_at": "2026-08-20T00:00:00+00:00"},
    ], tmp_path, "skills", DT)
    con = _con(str(tmp_path))
    from etl.aggregate import _skills_by_uid
    by, processed = _skills_by_uid(con, ["ashby:c:1"])
    con.close()
    assert by["ashby:c:1"] == {"Go"}          # v1's Python is superseded, not merged
    assert processed == {"ashby:c:1"}


def test_cache_state_splits_current_and_stale(tmp_path):
    from etl.skills import cache_state
    write_partition([
        {"job_uid": "a", "skill": "Python", "source": "llm",
         "prompt_version": "v1", "extracted_at": "x"},
        {"job_uid": "b", "skill": "Go", "source": "llm",
         "prompt_version": "v2", "extracted_at": "x"},
    ], tmp_path, "skills", DT)
    current, stale = cache_state(str(tmp_path), prompt_version="v2")
    assert current == {"b"} and stale == {"a"}   # 'a' is re-extractable, 'b' is done


def test_premium_carries_bootstrap_ci(tmp_path):
    con = _build(tmp_path, n_unprocessed=0)
    py = next(r for r in skill_premium(con, DT) if r["skill"] == "Python")
    con.close()
    assert py["ci_lo"] is not None and py["ci_hi"] is not None
    assert py["ci_lo"] <= py["premium_pct"] <= py["ci_hi"]
    assert "median_without_usd" not in py     # removed: it was pooled across strata (misleading)
