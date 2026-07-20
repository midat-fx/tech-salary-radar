"""Region / seniority / management / role-filter / dedup (PLAN.md §3.6, §3.7)."""

from etl.normalize import (
    build_snapshot_rows,
    is_management,
    job_uid,
    passes_role_filter,
    region_of,
    seniority_of,
)

RATES = {"USD": 1.0}


def test_seniority_buckets():
    assert seniority_of("Senior Software Engineer") == "senior"
    assert seniority_of("Staff Backend Engineer") == "staff+"
    assert seniority_of("Junior Data Analyst") == "junior"
    assert seniority_of("Mid-level Engineer") == "mid"
    assert seniority_of("Software Engineer") == "unspecified"     # no marker != mid


def test_is_management():
    assert is_management("Engineering Manager") is True
    assert is_management("Director of Data") is True
    assert is_management("Software Engineer") is False


def test_role_filter():
    assert passes_role_filter("Backend Engineer") is True
    assert passes_role_filter("Data Scientist") is True
    assert passes_role_filter("Software Engineer, Accounting") is True   # eng wins over soft-deny
    assert passes_role_filter("Account Executive") is False
    assert passes_role_filter("Sales Engineer") is False         # eng-adjacent hard-deny
    assert passes_role_filter("AI Partnerships Manager") is False  # GTM, despite "AI"
    assert passes_role_filter("Head of GTM, AI Inference") is False
    assert passes_role_filter("Product Manager") is False        # PM excluded
    assert passes_role_filter("Product Designer") is False       # design excluded
    assert passes_role_filter("Office Coordinator", department="Engineering") is False


def test_region_of():
    assert region_of("San Francisco, CA") == "us"
    assert region_of("London, United Kingdom") == "eu"
    assert region_of("Seoul, South Korea") == "other"
    assert region_of("Remote, US") == "us"


def test_job_uid():
    assert job_uid("ashby", "ramp", "abc") == "ashby:ramp:abc"


def test_snapshot_dedup_and_filter():
    jobs = [
        {"source": "ashby", "company": "x", "job_id": "1", "title": "Backend Engineer",
         "location_raw": "Remote, US", "is_remote": True, "raw_compensation": None},
        {"source": "ashby", "company": "x", "job_id": "1", "title": "Backend Engineer",
         "location_raw": "Remote, US", "is_remote": True, "raw_compensation": None},  # dup
        {"source": "ashby", "company": "x", "job_id": "2", "title": "Account Executive",
         "location_raw": "NYC", "is_remote": False, "raw_compensation": None},        # filtered
    ]
    rows, stats = build_snapshot_rows(jobs, RATES, "2026-08-20")
    assert len(rows) == 1                       # dup collapsed, non-tech filtered
    assert stats["filtered_non_tech"] == 1
    assert rows[0]["seniority"] == "unspecified" and rows[0]["region"] == "us"
