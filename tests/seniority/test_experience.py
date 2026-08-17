"""Years of experience: a second signal, and the one most likely to shrink
the unspecified bucket."""

from __future__ import annotations

import pytest

from etl.seniority import Seniority, extract_experience, level_from_years


class TestExtract:
    @pytest.mark.parametrize(
        "text,years",
        [
            ("5+ years of experience with distributed systems", 5),
            ("At least 4 years in a similar role", 4),
            ("Minimum of 7 years building backend services", 7),
            ("3-5 years of relevant experience", 3),
            ("8 yrs experience", 8),
            ("от 3 лет опыта", 3),
        ],
    )
    def test_the_wordings_postings_use(self, text, years):
        found = extract_experience(text)
        assert found is not None
        assert found.years == years

    def test_a_range_keeps_both_ends_but_bands_on_the_lower(self):
        # "3-5 years" is a posting that will take three; treating it as five
        # pushes a class of European mid-level adverts into senior.
        found = extract_experience("3-5 years of experience")
        assert (found.years, found.years_max) == (3, 5)
        assert found.level is Seniority.MID

    def test_a_number_without_a_unit_is_not_a_requirement(self):
        # A bare number in a job advert is anything at all.
        assert extract_experience("We are a team of 12 engineers") is None

    def test_a_company_age_is_not_a_requirement(self):
        assert extract_experience("Founded 10 years ago, we now serve millions") is None
        assert extract_experience("We have 3 years of runway") is None

    def test_an_implausible_number_is_refused(self):
        assert extract_experience("50 years of experience required") is None

    def test_the_headline_ask_wins_over_a_later_tool_requirement(self):
        # A later "2 years with Kubernetes" is about one tool, not the role.
        text = "Requirements: 6+ years of experience. Nice to have: 2 years with Kubernetes."
        assert extract_experience(text).years == 6

    def test_nothing_in_nothing_out(self):
        assert extract_experience(None) is None
        assert extract_experience("") is None
        assert extract_experience("We value curiosity") is None


class TestBands:
    @pytest.mark.parametrize(
        "years,level",
        [
            (0, Seniority.JUNIOR),
            (1, Seniority.JUNIOR),
            (2, Seniority.MID),
            (4, Seniority.MID),
            (5, Seniority.SENIOR),
            (7, Seniority.SENIOR),
            (8, Seniority.STAFF_PLUS),
            (15, Seniority.STAFF_PLUS),
        ],
    )
    def test_the_boundaries_these_postings_actually_use(self, years, level):
        assert level_from_years(years) is level

    def test_it_never_returns_unspecified(self):
        # A stated number is evidence; the point of extracting it is to have an
        # answer where the title had none.
        for years in range(0, 21):
            assert level_from_years(years) is not Seniority.UNSPECIFIED

    def test_the_requirement_describes_itself(self):
        assert "5+ years -> senior" in extract_experience("5+ years of experience").describe()
        assert "3-5 years" in extract_experience("3-5 years of experience").describe()
