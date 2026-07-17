"""Skeleton sanity checks (PLAN.md §7 stage 0): config and catalog import and stay self-consistent."""

from etl.config import SEARCH_KEYS, SEARCH_PLAN
from etl.skills_catalog import CANONICAL, SKILLS


def test_ru_plan_is_subset_of_search_keys():
    assert set(SEARCH_PLAN["ru"]) <= set(SEARCH_KEYS)


def test_canonical_matches_skills_order():
    assert CANONICAL == list(SKILLS)
