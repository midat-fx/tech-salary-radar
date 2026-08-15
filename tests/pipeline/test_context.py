"""The run's identity, and why it is decided once."""

from __future__ import annotations

from etl.pipeline import STAGE_ORDER, StageResult, build_context, by_source
from etl.testing import FixedClock, RecordingSleeper


class TestContext:
    def test_the_day_comes_from_the_clock_in_the_reporting_zone(self):
        ctx = build_context(clock=FixedClock(), sleeper=RecordingSleeper())
        assert ctx.day == "2026-08-19"

    def test_an_explicit_day_wins(self):
        ctx = build_context(day="2026-01-01", clock=FixedClock(), sleeper=RecordingSleeper())
        assert ctx.day == "2026-01-01"

    def test_the_day_does_not_move_under_a_run(self):
        # A run that built its own clock halfway down landed a snapshot in the
        # wrong partition when it crossed midnight.
        clock = FixedClock()
        ctx = build_context(clock=clock, sleeper=RecordingSleeper())
        clock.advance(days=1)
        assert ctx.day == "2026-08-19"

    def test_it_knows_where_a_partition_goes(self, tmp_path):
        ctx = build_context(data_dir=tmp_path, clock=FixedClock(), sleeper=RecordingSleeper())
        assert ctx.partition("snapshots").name == "dt=2026-08-19"

    def test_it_keeps_what_it_said(self):
        said = []
        ctx = build_context(clock=FixedClock(), sleeper=RecordingSleeper(), log=said.append)
        ctx.say("fetching")
        assert ctx.messages == ("fetching",)
        assert said == ["fetching"]

    def test_options_pass_through(self):
        ctx = build_context(
            clock=FixedClock(), sleeper=RecordingSleeper(), skip_llm=False, llm_limit=50
        )
        assert ctx.skip_llm is False and ctx.llm_limit == 50


class TestStages:
    def test_the_order_states_the_decisions_it_encodes(self):
        assert STAGE_ORDER.index("normalise") < STAGE_ORDER.index("dedupe")
        assert STAGE_ORDER.index("dedupe") < STAGE_ORDER.index("guard")
        assert STAGE_ORDER.index("guard") < STAGE_ORDER.index("write")
        assert STAGE_ORDER.index("fetch") < STAGE_ORDER.index("rates")

    def test_a_result_reads_as_a_boolean(self):
        assert StageResult("fetch")
        assert not StageResult("guard", ok=False, detail="ashby collapsed")

    def test_a_result_describes_itself(self):
        assert StageResult("guard", detail="clear").describe() == "guard: clear"
        assert StageResult("fetch").describe() == "fetch"

    def test_by_source_counts_the_shape_the_guard_compares(self):
        rows = [{"source": "ashby"}, {"source": "ashby"}, {"source": "lever"}]
        assert by_source(rows) == {"ashby": 2, "lever": 1}

    def test_an_empty_day_counts_nothing(self):
        assert by_source([]) == {}
