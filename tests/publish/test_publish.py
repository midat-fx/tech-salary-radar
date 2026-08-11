"""Writing a published file, and naming what a second publication is."""

from __future__ import annotations

from etl.publish import Kind, classify, dumps, eval_badge, jobs_badge, would_change, write_json


class TestWriter:
    def test_the_bytes_are_compact(self):
        # The browser downloads this on every page view.
        assert dumps({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'

    def test_non_ascii_stays_readable_in_a_diff(self):
        assert "Зарплаты" in dumps({"note": "Зарплаты"})

    def test_key_order_follows_the_builder_not_the_alphabet(self):
        # Sorting would be tidier and would make an accidental reordering
        # upstream invisible.
        assert dumps({"b": 1, "a": 2}) == '{"b":1,"a":2}'

    def test_an_unchanged_payload_produces_an_unchanged_file(self, tmp_path):
        write_json(tmp_path, "x.json", {"a": 1})
        assert not would_change(tmp_path / "x.json", {"a": 1})
        assert would_change(tmp_path / "x.json", {"a": 2})

    def test_a_missing_file_would_always_change(self, tmp_path):
        assert would_change(tmp_path / "nope.json", {})

    def test_it_creates_the_directory(self, tmp_path):
        out = write_json(tmp_path / "deep" / "deeper", "x.json", {"a": 1})
        assert out.exists()


class TestBadges:
    def test_a_normal_day_is_green_with_a_readable_number(self):
        badge = jobs_badge(6546)
        assert badge.message == "6 546"
        assert badge.color == "brightgreen"

    def test_an_empty_day_is_red(self):
        # A badge saying "0 jobs tracked" in green is the pipeline reporting its
        # own failure as a success.
        assert jobs_badge(0).color == "red"
        assert jobs_badge(0).message == "none"

    def test_the_shields_schema_is_version_one(self):
        assert jobs_badge(10).as_dict()["schemaVersion"] == 1

    def test_the_eval_badge_colours_against_the_threshold_ci_enforces(self):
        assert eval_badge(0.80).color == "brightgreen"
        assert eval_badge(0.60).color == "red"
        assert eval_badge(0.75).color == "brightgreen"

    def test_a_score_that_was_never_computed_says_so(self):
        assert eval_badge(None).message == "not run"
        assert eval_badge(None).color == "orange"


class TestRevision:
    def test_a_first_publication_is_named_as_such(self):
        assert classify("2026-08-19", False, True, False).kind is Kind.FIRST

    def test_the_same_rows_through_new_code_is_a_rebuild(self):
        rev = classify("2026-08-19", True, True, False)
        assert rev.kind is Kind.REBUILD
        assert not rev.needs_recording

    def test_changed_rows_after_publication_is_a_revision(self):
        # The case that has to leave a record: conflating it with a rebuild is
        # how a chart stops being reproducible from a commit.
        rev = classify("2026-08-19", True, True, True)
        assert rev.kind is Kind.REVISION
        assert rev.needs_recording

    def test_identical_output_is_worth_naming_too(self):
        rev = classify("2026-08-19", True, False, False)
        assert rev.kind is Kind.UNCHANGED
        assert "unchanged" in rev.describe()
