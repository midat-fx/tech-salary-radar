"""The remote flag, the location text, and what to do when they disagree."""

from __future__ import annotations

import pytest

from etl.geo import is_remote_text, read_remote


class TestFromTextAlone:
    @pytest.mark.parametrize(
        "location", ["Remote", "Remote - US", "Work from home", "Remote (Europe)", "Distributed"]
    )
    def test_the_wordings_that_mean_remote(self, location):
        assert is_remote_text(location)

    @pytest.mark.parametrize("location", ["Berlin, Germany", "San Francisco, CA (Hybrid)", ""])
    def test_the_wordings_that_do_not(self, location):
        assert not is_remote_text(location)

    def test_hybrid_beats_a_bare_remote(self):
        # "Remote or hybrid in Berlin" is not a remote posting for pay purposes.
        assert not is_remote_text("Remote or hybrid in Berlin")

    def test_an_anchored_remote_survives_a_hybrid_word(self):
        assert is_remote_text("Remote (US) — hybrid optional")


class TestFlagAndText:
    def test_a_board_that_has_the_field_is_believed(self):
        assert read_remote(True, "San Francisco, CA").is_remote
        assert not read_remote(False, "Berlin, Germany").is_remote

    def test_greenhouse_has_no_flag_so_the_text_decides(self):
        assert read_remote(None, "Remote - US").is_remote
        assert not read_remote(None, "Berlin, Germany").is_remote

    def test_a_flag_saying_remote_beside_a_hybrid_location_is_flagged_as_conflicting(self):
        # Both facts are true; collapsing them loses the one that decides which
        # pay market the posting belongs to.
        reading = read_remote(True, "San Francisco, CA (Hybrid)")
        assert reading.is_remote
        assert reading.conflicting

    def test_an_anchored_remote_is_not_a_conflict(self):
        reading = read_remote(True, "Remote (US)")
        assert reading.anchored
        assert not reading.conflicting

    def test_a_stale_false_flag_does_not_override_an_unambiguous_text(self):
        # A stale flag is more common than a location string that lies.
        assert read_remote(False, "Remote - EMEA").is_remote
        assert not read_remote(False, "Remote or hybrid, Berlin").is_remote
