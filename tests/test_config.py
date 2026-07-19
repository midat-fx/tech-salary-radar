"""Skeleton sanity checks (PLAN.md §7): config and catalog import and stay self-consistent."""

from etl.config import SALARY_MAX_USD, SALARY_MIN_USD, SOURCES
from etl.skills_catalog import CANONICAL, SKILLS


def test_sources_are_the_three_ats():
    assert set(SOURCES) == {"greenhouse", "lever", "ashby"}
    assert all("{slug}" in url for url in SOURCES.values())


def test_salary_sanity_bounds_ordered():
    assert 0 < SALARY_MIN_USD < SALARY_MAX_USD


def test_canonical_matches_skills_order():
    assert CANONICAL == list(SKILLS)
