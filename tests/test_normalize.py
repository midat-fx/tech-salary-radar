"""Region / seniority / management / role-filter / dedup (PLAN.md §3.6, §3.7)."""

import pytest

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


@pytest.mark.parametrize("loc,expected", [
    # "U.S." never matched before: the trailing dot breaks \b (30 rows sat in `other`)
    ("Remote U.S.", "us"), ("U.S. Remote", "us"), ("Remote - U.S.A.", "us"),
    # collisions: country Georgia / Canadian London / CA=Canada must not read as US
    ("Tbilisi, Georgia", "other"), ("Yerevan, Armenia", "other"),
    ("London, Ontario", "other"), ("Toronto, Canada", "other"), ("Vancouver, BC", "other"),
    # ...but the US state still wins when the city is American
    ("Atlanta, Georgia", "us"), ("Atlanta, GA", "us"),
    # city-only locations that used to fall into `other`
    ("Dublin", "eu"), ("Belgrade", "eu"), ("Kyiv", "eu"), ("Riga", "eu"),
    ("NYC", "us"), ("New York City", "us"), ("SF Bay Area", "us"),
    # genuinely unknown stays honest
    ("Remote", "other"), ("Hybrid", "other"), ("In-Office", "other"),
    ("Singapore", "other"), ("Tokyo, Japan", "other"),
])
def test_region_audit_rows(loc, expected):
    assert region_of(loc) == expected


@pytest.mark.parametrize("title,expected", [
    ("Software Engineer II, Backend", "mid"),
    ("Machine Learning Engineer II", "mid"),
    ("Data Analyst II", "mid"),
    ("Software Engineer 2", "mid"),
    ("Senior Engineer II", "senior"),          # word marker wins over the numeral
    ("Staff Engineer II", "staff+"),
    ("Software Engineer 3", "unspecified"),    # III/IV left alone: methodology decision
    ("Software Engineer I", "unspecified"),
    ("Engineer 1 - 2", "unspecified"),         # ambiguous range
    ("Software Engineer, L5", "unspecified"),  # level codes not mapped
    ("Member of Technical Staff", "unspecified"),   # MTS is an IC title, not staff+
    ("Senior Member of Technical Staff", "senior"),
])
def test_seniority_numerals_and_mts(title, expected):
    assert seniority_of(title) == expected


def test_mts_passes_role_filter():
    assert passes_role_filter("Member of Technical Staff") is True


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
