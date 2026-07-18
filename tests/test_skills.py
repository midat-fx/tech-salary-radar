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
