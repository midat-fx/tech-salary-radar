"""Reading a region out of the location strings the boards actually send."""

from __future__ import annotations

import pytest

from etl.geo import REGIONS, Certainty, Region, detect_region, region_of


class TestNamedPlaces:
    @pytest.mark.parametrize(
        "location",
        ["Berlin, Germany", "London, UK", "Amsterdam", "Kraków, Poland", "Remote - EMEA", "Zürich"],
    )
    def test_european_places(self, location):
        assert region_of(location) == "eu"

    @pytest.mark.parametrize(
        "location",
        ["San Francisco, CA", "New York, NY", "Austin, TX", "United States", "U.S.", "Seattle, WA"],
    )
    def test_us_places(self, location):
        assert region_of(location) == "us"

    @pytest.mark.parametrize("location", ["Bengaluru, India", "Tokyo", "São Paulo, Brazil"])
    def test_everywhere_else_is_one_bucket(self, location):
        # A fourth bucket for "unknown" would split the smallest sample further.
        assert region_of(location) == "other"


class TestCollisions:
    def test_a_canadian_city_named_after_a_european_one(self):
        # "london" is in the European table; Ontario is what breaks the tie.
        assert region_of("London, Ontario") == "other"

    def test_a_country_whose_name_is_also_a_us_state(self):
        assert region_of("Tbilisi, Georgia") == "other"

    def test_ca_meaning_canada_rather_than_california(self):
        assert region_of("Toronto, CA") == "other"

    def test_an_explicit_us_marker_breaks_the_collision_the_other_way(self):
        # "Vancouver, WA, United States" is a real place and really is the US.
        assert region_of("Vancouver, WA, United States") == "us"

    def test_the_collision_is_reported_as_such(self):
        guess = detect_region("London, Ontario")
        assert guess.region is Region.OTHER
        assert guess.certainty is Certainty.COLLIDED


class TestPrecedence:
    def test_europe_wins_when_a_string_matches_both(self):
        # The US table contains two-letter state codes, which collide with far
        # too much; European tokens are longer and therefore safer.
        assert region_of("Remote (EU), formerly Washington") == "eu"

    def test_the_country_field_is_considered_alongside_the_location(self):
        assert region_of("Remote", country="Germany") == "eu"


class TestAbsence:
    @pytest.mark.parametrize("location", [None, "", "   ", "Remote", "Anywhere"])
    def test_nothing_recognisable_is_other_and_says_so(self, location):
        guess = detect_region(location)
        assert guess.region is Region.OTHER
        assert guess.certainty is Certainty.ABSENT

    def test_absent_and_collided_are_told_apart(self):
        # Both store as "other", but a run where one share jumps means a board
        # stopped sending locations, and the other means nothing of the sort.
        assert detect_region("Remote").certainty is not detect_region("Toronto, CA").certainty


def test_every_verdict_is_a_storable_bucket():
    for location in ["Berlin", "Austin, TX", "Toronto, CA", "", "Mars"]:
        assert region_of(location) in REGIONS
