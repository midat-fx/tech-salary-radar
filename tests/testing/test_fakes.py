"""The fakes have their own tests: a double that stops recording turns every
suite that uses it green for the wrong reason."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from etl.sources import ashby, greenhouse
from etl.testing import (
    DEFAULT_NOW,
    FixedClock,
    JobSpec,
    QuotaExhausted,
    RecordedBoard,
    RecordingSleeper,
    ScriptedLabeller,
    board_client,
    build_dataset,
    keyword_labeller,
    load_fixture,
)


class TestFixedClock:
    def test_it_only_moves_when_the_test_moves_it(self):
        clock = FixedClock()
        assert clock.now() == DEFAULT_NOW == clock.now()
        clock.advance(days=1)
        assert clock.now() == datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)

    def test_today_ignores_the_zone_on_purpose(self):
        # A fake that applied a real timezone would put back the thing the port
        # exists to remove: a result that depends on which side of midnight the
        # machine happens to be.
        clock = FixedClock()
        assert clock.today("Pacific/Kiritimati") == clock.today("Pacific/Niue")

    def test_advance_and_set_chain(self):
        clock = FixedClock().advance(hours=2).set(DEFAULT_NOW)
        assert clock.now() == DEFAULT_NOW


class TestRecordingSleeper:
    def test_it_records_rather_than_waits(self):
        sleeper = RecordingSleeper()
        sleeper.sleep(1.5)
        sleeper.sleep(3.0)
        assert sleeper.pauses == [1.5, 3.0]
        assert sleeper.total == 4.5
        assert sleeper.count == 2


class TestBoardClient:
    def test_a_scripted_board_answers_its_recorded_payload(self):
        client, handler = board_client(
            {"acme": RecordedBoard(payload=load_fixture("greenhouse.json"))}
        )
        jobs = greenhouse.fetch(client, "acme", RecordingSleeper())
        assert jobs
        assert handler.call_count == 1
        assert all(job["source"] == "greenhouse" for job in jobs)

    def test_an_unscripted_slug_is_a_deleted_board(self):
        # The realistic default: the seed is older than the boards it names.
        client, _ = board_client({})
        assert greenhouse.fetch(client, "gone", RecordingSleeper()) == []

    def test_a_scripted_status_is_returned(self):
        client, _ = board_client({"acme": RecordedBoard(status=404)})
        assert ashby.fetch(client, "acme", RecordingSleeper()) == []

    def test_the_transport_records_what_was_requested(self):
        client, handler = board_client({"acme": RecordedBoard(payload={"jobs": []})})
        greenhouse.fetch(client, "acme", RecordingSleeper())
        assert "acme" in handler.board_requests[0]

    def test_it_serves_rates_too_because_every_run_fetches_them(self):
        from etl.fx import fetch_rates
        from etl.testing import FixedClock

        client, _ = board_client({})
        assert fetch_rates(client, "/tmp", FixedClock()).get("GBP") == 0.79

    def test_rates_can_be_switched_off_to_drive_the_dead_cascade(self):
        from etl.fx import FxError, fetch_rates
        from etl.testing import FixedClock

        client, _ = board_client({}, rates=None)
        with pytest.raises(FxError):
            fetch_rates(client, "/tmp/nonexistent-fx-dir", FixedClock())


class TestScriptedLabeller:
    def test_it_answers_from_the_script_and_records_the_batch(self):
        labeller = keyword_labeller(Django=["Python", "Django"])
        result = labeller([{"id": 0, "title": "Dev", "text": "We use Django"}])
        assert result["items"] == [{"id": 0, "skills": ["Python", "Django"]}]
        assert labeller.batch_sizes == [1]

    def test_an_unmatched_posting_gets_an_empty_list_not_a_missing_id(self):
        labeller = keyword_labeller(Django=["Python"])
        result = labeller([{"id": 0, "title": "Dev", "text": "We use COBOL"}])
        assert result["items"] == [{"id": 0, "skills": []}]

    def test_it_can_be_told_to_drop_an_id(self):
        # The misbehaviour that used to poison the cache with null rows.
        labeller = ScriptedLabeller(answers={}, omit={"COBOL"})
        result = labeller([{"id": 0, "title": "x", "text": "COBOL"}, {"id": 1, "title": "y", "text": "Go"}])
        assert [item["id"] for item in result["items"]] == [1]

    def test_it_can_be_told_to_fail(self):
        labeller = ScriptedLabeller(failures=[QuotaExhausted()])
        with pytest.raises(QuotaExhausted):
            labeller([{"id": 0, "title": "x", "text": "y"}])
        # the failure list is consumed, so the next call succeeds
        assert labeller([{"id": 0, "title": "x", "text": "y"}])["items"]

    def test_the_quota_error_carries_the_text_the_caller_matches_on(self):
        # Stopping for the day rather than burning retries depends on this.
        assert "429" in str(QuotaExhausted())


class TestDataset:
    def test_it_writes_partitions_the_schema_accepts(self, tmp_path):
        con = build_dataset(
            tmp_path,
            {
                "2026-08-18": [JobSpec("ashby:acme:1", salary=200_000, skills=["Python"])],
                "2026-08-19": [
                    JobSpec("ashby:acme:1", salary=200_000, skills=["Python"]),
                    JobSpec("ashby:acme:2", salary=None, skills=None),
                ],
            },
        )
        assert con.execute("SELECT count(*) FROM snap").fetchone()[0] == 3
        assert con.execute("SELECT count(DISTINCT job_uid) FROM jobs").fetchone()[0] == 2

    def test_first_seen_is_the_day_a_job_appeared_not_every_day(self, tmp_path):
        con = build_dataset(
            tmp_path,
            {
                "2026-08-18": [JobSpec("ashby:acme:1", salary=1_000_00.0)],
                "2026-08-19": [JobSpec("ashby:acme:1", salary=1_000_00.0)],
            },
        )
        assert con.execute("SELECT min(first_seen) FROM jobs").fetchone()[0] == "2026-08-18"

    def test_never_labelled_and_labelled_empty_are_different(self, tmp_path):
        # The distinction ADR 0003 is built on, so the fake has to carry it.
        con = build_dataset(
            tmp_path,
            {
                "2026-08-19": [
                    JobSpec("ashby:acme:1", salary=200_000.0, skills=None),
                    JobSpec("ashby:acme:2", salary=200_000.0, skills=[]),
                ]
            },
        )
        rows = con.execute("SELECT job_uid, skill FROM sk").fetchall()
        assert rows == [("ashby:acme:2", None)]
