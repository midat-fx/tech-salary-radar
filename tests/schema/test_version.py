"""Reading a day written by older code is a declared behaviour, not luck."""

from __future__ import annotations

import pytest

from etl.schema import HISTORY, SCHEMA_VERSION, Compatibility, SchemaVersion, compatibility
from etl.schema.version import ASSUMED_FOR_UNMARKED, describe, is_readable

V = SchemaVersion


class TestParsing:
    def test_reads_the_stamped_form(self):
        assert V.parse("1.3") == V(1, 3)
        assert V.parse("  2.0 ") == V(2, 0)

    @pytest.mark.parametrize("raw", [None, "", "1", "1.2.3", "one.two", "1.x"])
    def test_anything_unstamped_is_absent_rather_than_an_error(self, raw):
        # Partitions from the first days carry no marker at all; that is a
        # handled state, not a crash.
        assert V.parse(raw) is None

    def test_versions_order_by_major_then_minor(self):
        assert V(1, 2) < V(1, 10) < V(2, 0)
        assert str(V(1, 3)) == "1.3"


class TestCompatibility:
    def test_the_same_version_is_an_exact_match(self):
        assert compatibility(SCHEMA_VERSION) == Compatibility.EXACT

    def test_an_older_minor_is_read_with_defaults(self):
        assert compatibility(V(1, 0), V(1, 3)) == Compatibility.OLDER_FILL_DEFAULTS

    def test_a_newer_minor_is_read_by_ignoring_what_it_added(self):
        # A partition written by a deploy that was then rolled back. The shared
        # columns still mean the same thing — that is what a minor promises.
        assert compatibility(V(1, 5), V(1, 3)) == Compatibility.NEWER_IGNORE_EXTRA

    def test_a_different_major_is_refused_in_both_directions(self):
        assert compatibility(V(2, 0), V(1, 3)) == Compatibility.INCOMPATIBLE
        assert compatibility(V(1, 3), V(2, 0)) == Compatibility.INCOMPATIBLE

    def test_an_unmarked_partition_is_read_as_the_first_version(self):
        assert compatibility(None, V(1, 3)) == compatibility(ASSUMED_FOR_UNMARKED, V(1, 3))
        assert ASSUMED_FOR_UNMARKED == V(1, 0)

    def test_readability_is_exactly_the_major_rule(self):
        assert is_readable(V(1, 0))
        assert is_readable(V(1, 99))
        assert is_readable(None)
        assert not is_readable(V(0, 9))
        assert not is_readable(V(2, 0))


class TestDescribe:
    def test_each_verdict_says_what_will_happen_to_the_day(self):
        assert "exact" in describe(SCHEMA_VERSION)
        assert "filled with defaults" in describe(V(1, 0), V(1, 3))
        assert "ignored" in describe(V(1, 9), V(1, 3))
        assert "refusing" in describe(V(2, 0), V(1, 3))

    def test_an_unmarked_day_says_so_rather_than_inventing_a_number(self):
        assert "unmarked" in describe(None)


class TestHistory:
    def test_every_version_up_to_the_current_one_is_explained(self):
        # The changelog is what tells a reader what a missing column means for
        # a given day; a gap in it makes a fill unexplainable.
        minors = sorted(v.minor for v in HISTORY if v.major == SCHEMA_VERSION.major)
        assert minors == list(range(SCHEMA_VERSION.minor + 1))

    def test_the_current_version_is_in_the_history(self):
        assert SCHEMA_VERSION in HISTORY
        assert HISTORY[SCHEMA_VERSION]

    def test_no_entry_is_an_empty_sentence(self):
        for version, note in HISTORY.items():
            assert note.strip(), version
