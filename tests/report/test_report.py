"""The report's shape is a contract: a field that moves breaks callers quietly."""

from __future__ import annotations

from etl.dedupe import DedupeReport
from etl.guards import CircuitBreaker, Severity, Verdict
from etl.report import SECTIONS, collect, field_names, format_value, render, section_of
from etl.report.fields import Field
from etl.skills import ExtractionStats


def a_run(**over):
    base = dict(
        day="2026-08-19",
        seed_size=320,
        raw_jobs=16_500,
        snapshot_rows=6_546,
        new_rows=412,
        with_salary=1_431,
        filtered_non_tech=9_954,
        skill_rows=700,
    )
    base.update(over)
    return collect(**base)


class TestShape:
    def test_every_declared_field_appears_in_the_text(self):
        text = a_run().text()
        for field in (f for fields in SECTIONS.values() for f in fields):
            assert field.label in text, field.key

    def test_the_field_names_are_unique(self):
        names = field_names()
        assert len(names) == len(set(names))

    def test_every_field_belongs_to_exactly_one_section(self):
        for name in field_names():
            assert section_of(name) is not None
        assert section_of("not_a_field") is None

    def test_a_stage_that_did_not_run_still_prints_its_lines(self):
        # The line count is the same whether or not a stage ran, so a diff of
        # two runs lines up.
        text = a_run().text()
        assert text.count("\n") == a_run(skill_rows=0).text().count("\n")

    def test_the_same_numbers_render_identically_twice(self):
        assert a_run().text() == a_run().text()


class TestFormatting:
    def test_an_absent_value_is_a_dash_not_a_missing_line(self):
        assert format_value(Field("k", "l"), None) == "-"

    def test_a_share_prints_to_one_decimal(self):
        # A share wobbling in the fourth place makes a diff unreadable.
        assert format_value(Field("k", "l", "share"), 0.21857) == "21.9%"

    def test_a_list_prints_sorted(self):
        # Dict iteration order is not something to publish.
        assert format_value(Field("k", "l", "list"), ["b", "a"]) == "a, b"
        assert format_value(Field("k", "l", "list"), {"b": 2, "a": 1}) == "a=1, b=2"

    def test_an_empty_list_is_a_dash(self):
        assert format_value(Field("k", "l", "list"), []) == "-"
        assert format_value(Field("k", "l", "list"), {}) == "-"

    def test_blank_text_is_a_dash_rather_than_an_empty_line(self):
        assert format_value(Field("k", "l", "text"), "   ") == "-"


class TestCollect:
    def test_the_salary_share_is_derived_not_supplied(self):
        report = a_run()
        assert report["salary_share"] == 1_431 / 6_546

    def test_an_empty_day_does_not_divide_by_zero(self):
        assert a_run(snapshot_rows=0, with_salary=0)["salary_share"] is None

    def test_pay_refusals_are_summarised_by_reason(self):
        report = collect(
            day="d", seed_size=1, raw_jobs=1, snapshot_rows=1, new_rows=0, with_salary=0,
            pay_stats={"pay_accepted": 5, "pay_empty": 90, "pay_below_floor": 3, "pay_implausible_spread": 2},
        )
        assert report["pay_rejected"] == 5
        assert report["pay_reasons"] == {"below_floor": 3, "implausible_spread": 2}

    def test_accepted_and_empty_are_not_counted_as_refusals(self):
        # Most postings simply have no salary; that is not a parser failure.
        report = collect(
            day="d", seed_size=1, raw_jobs=1, snapshot_rows=1, new_rows=0, with_salary=0,
            pay_stats={"pay_accepted": 5, "pay_empty": 90},
        )
        assert report["pay_rejected"] == 0

    def test_it_reads_the_breaker_the_dedupe_and_the_guards(self):
        breaker = CircuitBreaker()
        breaker.record_success("ashby")
        report = a_run(
            breaker=breaker,
            dedupe=DedupeReport(rows_in=10, rows_out=9, duplicates_removed=1),
            guards=Verdict().add("volume", Severity.WARN, "new source"),
        )
        assert report["boards_reached"] == 1
        assert report["duplicates_removed"] == 1
        assert report["guard_verdict"] == "clear"
        assert "new source" in report["guard_findings"][0]

    def test_a_refusal_shows_as_refused(self):
        report = a_run(guards=Verdict().add("volume", Severity.REFUSE, "ashby collapsed"))
        assert report["guard_verdict"] == "refused"

    def test_it_reads_the_extraction_statistics(self):
        stats = ExtractionStats(queue_depth=900, extracted=500, missing_ids=3)
        report = a_run(llm_stats=stats)
        assert (report["llm_queue_depth"], report["llm_extracted"]) == (900, 500)
        assert report["llm_missing_ids"] == 3

    def test_the_machine_form_is_the_values_not_the_prose(self):
        # last_run.json is read back by the aggregator; re-parsing prose would
        # be an odd way to move a number between two parts of one program.
        assert a_run().as_dict()["snapshot_rows"] == 6_546


class TestRenderDirectly:
    def test_a_title_is_optional(self):
        assert render({}, "=== run ===").startswith("=== run ===")
        assert not render({}).startswith("===")

    def test_sections_are_separated_by_a_blank_line(self):
        text = render({})
        assert "\n\ncrawl:" in text or text.startswith("crawl:")
        assert "\n\nfilter:" in text
