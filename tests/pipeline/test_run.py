"""The one place the layers meet, driven end to end against the fakes."""

from __future__ import annotations

import json

import pytest

from etl.pipeline import GuardRefused, build_context, execute
from etl.publish import read_partition
from etl.testing import FixedClock, RecordedBoard, RecordingSleeper, board_client, load_fixture

SEED = [{"source": "greenhouse", "slug": "acme", "name": "Acme"}]


def a_context(tmp_path, **over):
    return build_context(
        data_dir=tmp_path,
        clock=FixedClock(),
        sleeper=RecordingSleeper(),
        log=lambda *_: None,
        pause=0,
        **over,
    )


def a_client(payload=None):
    return board_client({"acme": RecordedBoard(payload=payload or load_fixture("greenhouse.json"))})[0]


class TestHappyPath:
    def test_a_day_is_written_and_reported(self, tmp_path):
        outcome = execute(a_context(tmp_path), a_client(), SEED, set())
        assert outcome.snapshot_rows > 0
        assert read_partition(tmp_path, "snapshots", "2026-08-19")
        assert "run 2026-08-19" in outcome.text()

    def test_everything_is_new_on_the_first_day(self, tmp_path):
        outcome = execute(a_context(tmp_path), a_client(), SEED, set())
        assert outcome.new_rows == outcome.snapshot_rows

    def test_nothing_is_new_when_the_uids_are_already_known(self, tmp_path):
        first = execute(a_context(tmp_path), a_client(), SEED, set())
        known = {row["job_uid"] for row in read_partition(tmp_path, "snapshots", "2026-08-19")}
        second = execute(a_context(tmp_path), a_client(), SEED, known)
        assert first.new_rows > 0
        assert second.new_rows == 0

    def test_the_run_writes_its_numbers_for_the_aggregator(self, tmp_path):
        execute(a_context(tmp_path), a_client(), SEED, set())
        cached = json.loads((tmp_path / "cache" / "last_run.json").read_text())
        assert cached["date"] == "2026-08-19"
        assert cached["snapshot_rows"] > 0

    def test_the_day_comes_from_the_context_not_the_wall_clock(self, tmp_path):
        outcome = execute(a_context(tmp_path, day="2026-01-05"), a_client(), SEED, set())
        assert read_partition(tmp_path, "snapshots", "2026-01-05")
        assert "2026-01-05" in outcome.text()

    def test_the_crawl_pauses_through_the_injected_sleeper(self, tmp_path):
        ctx = build_context(
            data_dir=tmp_path, clock=FixedClock(), sleeper=RecordingSleeper(), log=lambda *_: None
        )
        seed = SEED + [{"source": "greenhouse", "slug": "other", "name": "Other"}]
        execute(ctx, a_client(), seed, set())
        assert ctx.sleeper.count >= 1


class TestOrdering:
    def test_deduplication_happens_before_the_guards(self, tmp_path):
        # Comparing de-duplicated rows against a non-de-duplicated history would
        # read the correction as a collapse and refuse the first correct day.
        outcome = execute(a_context(tmp_path), a_client(), SEED, set())
        assert outcome.dedupe.rows_in >= outcome.dedupe.rows_out
        assert outcome.verdict.ok

    def test_nothing_is_written_when_a_guard_refuses(self, tmp_path):
        for day in ("2026-08-15", "2026-08-16", "2026-08-17", "2026-08-18"):
            execute(a_context(tmp_path, day=day), a_client(), SEED, set())
        empty = a_client({"jobs": []})
        with pytest.raises(GuardRefused):
            execute(a_context(tmp_path, day="2026-08-19"), empty, SEED, set())
        assert read_partition(tmp_path, "snapshots", "2026-08-19") == []


class TestEmptyBoards:
    def test_a_seed_of_dead_boards_produces_a_refusal_not_a_crash(self, tmp_path):
        client, _ = board_client({})
        with pytest.raises(GuardRefused, match="no rows"):
            execute(a_context(tmp_path), client, SEED, set())

    def test_the_report_survives_a_board_that_answers_nothing(self, tmp_path):
        execute(a_context(tmp_path), a_client(), SEED, set())
        outcome = execute(a_context(tmp_path, day="2026-08-20"), a_client(), SEED, set())
        assert "postings fetched" in outcome.text()


class TestFreshness:
    def test_a_stale_rate_table_warns_without_stopping_the_day(self, tmp_path):
        # Every converted figure rests on it, and the run says so — but a day of
        # real postings is worth more than a perfectly current rate.
        ctx = a_context(tmp_path)
        outcome = execute(ctx, a_client(), SEED, set())
        assert outcome.verdict.ok

    def test_rows_dated_off_the_partition_stop_the_write(self, tmp_path):
        from etl.guards import check_freshness

        rows = [{"snapshot_date": "2026-08-18", "published_at": None}]
        verdict = check_freshness(rows, "2026-08-19", "2026-08-19", FixedClock().now())
        assert not verdict.ok
