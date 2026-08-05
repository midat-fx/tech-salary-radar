"""Tidying a location enough that two boards' spellings of one city match."""

from __future__ import annotations

from etl.geo import location_tokens, normalise_location


class TestNormalise:
    def test_it_casefolds_and_collapses_whitespace(self):
        assert normalise_location("  San   Francisco, CA  ") == "san francisco, ca"

    def test_accents_are_stripped_so_two_spellings_of_one_city_match(self):
        assert normalise_location("Zürich") == normalise_location("Zurich")
        assert normalise_location("Kraków") == normalise_location("Krakow")

    def test_nothing_is_dropped_here(self):
        # The region tables are matched against this output, so removing a word
        # could move a posting between buckets.
        assert "ontario" in normalise_location("London, Ontario")

    def test_empty_input_is_an_empty_string(self):
        assert normalise_location(None) == ""
        assert normalise_location("") == ""


class TestTokens:
    def test_the_same_place_written_two_ways_gives_one_tuple(self):
        assert location_tokens("San Francisco, CA (Hybrid)") == location_tokens(
            "Hybrid — CA, San Francisco"
        )

    def test_arrangement_words_are_removed_but_places_are_not(self):
        tokens = location_tokens("Remote - Berlin, Germany")
        assert "berlin" in tokens
        assert "germany" in tokens
        assert not any("remote" in t for t in tokens)

    def test_the_order_is_stable_because_boards_disagree_about_it(self):
        assert location_tokens("Berlin, Germany") == location_tokens("Germany, Berlin")

    def test_a_parenthetical_is_kept_as_a_token_not_thrown_away(self):
        assert "eu" in location_tokens("Remote (EU)")

    def test_nothing_in_nothing_out(self):
        assert location_tokens(None) == ()
        assert location_tokens("  (Remote)  ") == ()
