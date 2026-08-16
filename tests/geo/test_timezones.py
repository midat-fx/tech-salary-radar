"""Which working hours a remote posting expects — a pay question, not a detail."""

from __future__ import annotations

import pytest

from etl.geo import Anchor, detect_timezone


class TestNamedZones:
    @pytest.mark.parametrize(
        "text",
        ["Remote (US, Pacific Time)", "Remote — must overlap PST", "Remote, US hours", "Americas"],
    )
    def test_american_hours(self, text):
        assert detect_timezone(text).anchor is Anchor.AMERICAS

    @pytest.mark.parametrize(
        "text", ["Remote (CET)", "Remote — European time zones", "Remote, UK hours", "GMT overlap"]
    )
    def test_european_hours(self, text):
        assert detect_timezone(text).anchor is Anchor.EUROPE

    @pytest.mark.parametrize("text", ["Remote (JST)", "Remote — APAC hours", "SGT overlap"])
    def test_asia_pacific_hours(self, text):
        assert detect_timezone(text).anchor is Anchor.ASIA_PACIFIC

    def test_a_genuinely_global_role_says_so(self):
        hint = detect_timezone("Remote — any time zone, fully async")
        assert hint.anchor is Anchor.ANYWHERE
        assert not hint.is_anchored


class TestOffsets:
    def test_an_offset_maps_to_the_nearest_market(self):
        assert detect_timezone("Remote UTC-5").anchor is Anchor.AMERICAS
        assert detect_timezone("Remote UTC+2").anchor is Anchor.EUROPE
        assert detect_timezone("Remote UTC+8").anchor is Anchor.ASIA_PACIFIC

    def test_the_offset_itself_is_kept(self):
        hint = detect_timezone("Remote GMT+3")
        assert hint.offset_hours == 3
        assert hint.source == "offset"

    def test_utc_itself_is_european_hours(self):
        # The boundaries are where the working day stops overlapping.
        assert detect_timezone("Remote UTC+0").anchor is Anchor.EUROPE

    def test_a_named_zone_beats_an_offset_in_the_same_string(self):
        assert detect_timezone("Remote (PST), roughly UTC+2").anchor is Anchor.AMERICAS


class TestUnstated:
    @pytest.mark.parametrize("text", [None, "", "Remote", "Berlin, Germany"])
    def test_nothing_said_is_not_the_same_as_anywhere(self, text):
        # "Remote" alone is the common case; "any time zone" is rare and means
        # something quite different about who can apply.
        hint = detect_timezone(text)
        assert hint.anchor is Anchor.UNSTATED
        assert not hint.is_anchored

    def test_no_city_is_ever_inferred_from(self):
        # A city-to-zone table would immediately disagree with the region tables
        # next door, which is why nothing is inferred from a place name.
        assert detect_timezone("San Francisco, CA").anchor is Anchor.UNSTATED
