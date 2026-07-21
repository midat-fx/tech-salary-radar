"""LLM response parsing / canonicalization (PLAN.md §6). Real Gemini not called here."""

from etl.skills import extract_for_jobs, extract_llm
from etl.skills_catalog import canonicalize


def test_canonicalize_exact_only():
    assert canonicalize("питон") == "Python"
    assert canonicalize("REACT") == "React"
    assert canonicalize("pythonic") is None     # not a substring match
    assert canonicalize("nope") is None


def test_extract_llm_maps_and_drops_unknown():
    def fake_call(_payload):
        return {"items": [{"id": 0, "skills": ["python", "React", "garbage"]},
                          {"id": 1, "skills": []}]}
    out = extract_llm([{"id": 0, "title": "x", "text": "y"},
                       {"id": 1, "title": "a", "text": "b"}], call=fake_call)
    assert out[0] == ["Python", "React"] and out[1] == []


def test_extract_for_jobs_rows_and_cache_skip():
    jobs = [{"source": "ashby", "company": "c", "job_id": "1", "title": "Backend Engineer",
             "description": "We use Python and Kubernetes."},
            {"source": "ashby", "company": "c", "job_id": "2", "title": "SRE",
             "description": "No tools listed."}]

    def fake_call(payload):
        # id 0 -> skills, id 1 -> none
        return {"items": [{"id": 0, "skills": ["Python", "Kubernetes"]}, {"id": 1, "skills": []}]}

    rows = extract_for_jobs(jobs, processed_uids=set(), call=fake_call, pause=0)
    uids = {r["job_uid"] for r in rows}
    assert "ashby:c:1" in uids and "ashby:c:2" in uids
    # job 2 processed but no skills -> exactly one NULL row
    assert [r["skill"] for r in rows if r["job_uid"] == "ashby:c:2"] == [None]
    # already-processed jobs are skipped
    assert extract_for_jobs(jobs, processed_uids={"ashby:c:1", "ashby:c:2"}, call=fake_call, pause=0) == []


def _job(source, jid, desc="We use Python."):
    return {"source": source, "company": "c", "job_id": jid, "title": "Backend Engineer",
            "description": desc}


def test_salary_bearing_jobs_are_labelled_first():
    """The flagship metric only consumes salary-bearing jobs — they must win the daily budget."""
    jobs = [_job("ashby", "nosal"), _job("ashby", "sal_old"), _job("ashby", "sal_new")]
    priority = {"ashby:c:nosal": (False, "2026-07-19T00:00:00+00:00"),
                "ashby:c:sal_old": (True, "2026-01-01T00:00:00+00:00"),
                "ashby:c:sal_new": (True, "2026-07-19T00:00:00+00:00")}
    sent = []

    def fake_call(payload):
        sent.extend(payload)
        return {"items": [{"id": p["id"], "skills": ["Python"]} for p in payload]}

    rows = extract_for_jobs(jobs, processed_uids=set(), limit=2, call=fake_call, pause=0,
                            priority=priority)
    labelled = {r["job_uid"] for r in rows}
    assert labelled == {"ashby:c:sal_new", "ashby:c:sal_old"}   # the salary-less job waits
    assert len(sent) == 2


def test_sources_are_interleaved():
    jobs = [_job("ashby", "a1"), _job("ashby", "a2"), _job("greenhouse", "g1")]

    def fake_call(payload):
        return {"items": [{"id": p["id"], "skills": []} for p in payload]}

    rows = extract_for_jobs(jobs, processed_uids=set(), limit=2, call=fake_call, pause=0)
    sources = {r["job_uid"].split(":")[0] for r in rows}
    assert sources == {"ashby", "greenhouse"}    # not two ashby jobs


def test_missing_id_is_not_cached_as_null():
    """A silently dropped id must stay queued, not get a NULL row that poisons the cache forever."""
    jobs = [_job("ashby", "1"), _job("ashby", "2")]

    def fake_call(payload):
        return {"items": [{"id": 0, "skills": ["Python"]}]}      # id 1 omitted

    rows = extract_for_jobs(jobs, processed_uids=set(), call=fake_call, pause=0)
    assert {r["job_uid"] for r in rows} == {"ashby:c:1"}


def test_empty_description_is_not_sent():
    jobs = [_job("ashby", "1", desc="   ")]

    def fake_call(payload):
        raise AssertionError("must not be called")

    assert extract_for_jobs(jobs, processed_uids=set(), call=fake_call, pause=0) == []
