"""Reading a level out of a title, including the ones that must not be read."""

from __future__ import annotations

import pytest

from etl.seniority import (
    ORDER,
    SENIORITIES,
    Seniority,
    detect_seniority,
    is_management,
    is_ranked,
    rank,
    seniority_of,
)


class TestWordMarkers:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Staff Software Engineer", "staff+"),
            ("Principal Engineer", "staff+"),
            ("Engineering Lead", "staff+"),
            ("Distinguished Engineer", "staff+"),
            ("Senior Backend Engineer", "senior"),
            ("Sr. Data Scientist", "senior"),
            ("Junior Developer", "junior"),
            ("Software Engineering Intern", "junior"),
            ("New Grad Software Engineer", "junior"),
            ("Mid-level Python Developer", "mid"),
            ("Intermediate QA Engineer", "mid"),
        ],
    )
    def test_the_words_that_carry_a_level(self, title, expected):
        assert seniority_of(title) == expected


class TestNumerals:
    def test_a_numeral_attached_to_the_role_noun_is_mid(self):
        assert seniority_of("Software Engineer II") == "mid"
        assert seniority_of("Data Analyst 2") == "mid"

    def test_a_word_marker_beats_a_numeral(self):
        # "Senior Engineer II" is senior; the numeral is a sub-level inside it.
        assert seniority_of("Senior Engineer II") == "senior"

    def test_a_company_ladder_code_is_not_guessed(self):
        # L5 at one company is not L5 at another. ADR 0006.
        assert seniority_of("Software Engineer, L5") == "unspecified"
        assert seniority_of("Engineer IC3") == "unspecified"
        assert seniority_of("Backend Engineer E4") == "unspecified"

    def test_a_range_of_numerals_is_not_a_level(self):
        assert seniority_of("Engineer 1 - 2") == "unspecified"

    def test_the_reason_distinguishes_a_read_level_from_an_unread_one(self):
        # Both store as unspecified; one means "nothing said" and the other
        # means "said something we refuse to interpret".
        assert detect_seniority("Backend Engineer").rule == "no-marker"
        assert detect_seniority("Backend Engineer L5").rule == "ambiguous-numeral"


class TestMemberOfTechnicalStaff:
    def test_it_is_not_a_staff_level_despite_the_word(self):
        # Left to the word list, every AI lab's whole engineering org is staff+.
        assert seniority_of("Member of Technical Staff") == "unspecified"
        assert seniority_of("MTS, Inference") == "unspecified"

    def test_a_senior_prefix_still_reads(self):
        assert seniority_of("Senior Member of Technical Staff") == "senior"

    def test_the_rule_is_named_so_the_exception_is_visible(self):
        assert detect_seniority("Member of Technical Staff").rule == "mts"


class TestEmpty:
    @pytest.mark.parametrize("title", [None, "", "   "])
    def test_no_title_is_unspecified(self, title):
        assert seniority_of(title) == "unspecified"
        assert detect_seniority(title).rule == "empty"


class TestManagement:
    @pytest.mark.parametrize(
        "title",
        ["Engineering Manager", "Director of Engineering", "VP of Product", "Head of Data", "CTO"],
    )
    def test_management_titles_are_recognised(self, title):
        assert is_management(title)

    @pytest.mark.parametrize("title", ["Staff Engineer", "Senior Developer", "Product Manager"])
    def test_ic_titles_are_not(self, title):
        assert is_management(title) is (title == "Product Manager")

    def test_a_manager_still_gets_a_seniority_read(self):
        # It is excluded from the salary statistics, not from the row.
        assert seniority_of("Senior Engineering Manager") == "senior"


class TestVocabulary:
    def test_every_reading_is_a_storable_bucket(self):
        for title in ["Staff Engineer", "Sr. Dev", "Intern", "Engineer II", "Engineer L5", ""]:
            assert seniority_of(title) in SENIORITIES

    def test_unspecified_has_no_place_in_the_ladder(self):
        # Sorting it anywhere implies it means something.
        assert Seniority.UNSPECIFIED not in ORDER
        assert rank(Seniority.UNSPECIFIED) is None
        assert not is_ranked("unspecified")

    def test_the_four_levels_are_ordered_as_a_ladder(self):
        assert [rank(level) for level in ORDER] == [0, 1, 2, 3]
        assert rank("junior") < rank("mid") < rank("senior") < rank("staff+")
