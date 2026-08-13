"""Probing a candidate board, and choosing between two that answer."""

from __future__ import annotations

from etl.sources.discovery import BoardStatus, Probe, classify_payload, dedupe_candidates
from etl.testing import RecordedBoard, RecordingSleeper, board_client, load_fixture


class TestClassify:
    def test_a_board_with_postings_is_active(self):
        probe = classify_payload("greenhouse", "acme", load_fixture("greenhouse.json"))
        assert probe.status is BoardStatus.ACTIVE
        assert probe.n_jobs > 0
        assert probe.is_usable

    def test_a_board_with_no_postings_is_empty_not_dead(self):
        # The board exists; the company is not hiring. A re-check needs to know
        # it was seen, so it stays in the file.
        probe = classify_payload("greenhouse", "acme", {"jobs": []})
        assert probe.status is BoardStatus.EMPTY
        assert not probe.is_usable

    def test_a_missing_board_is_dead(self):
        assert classify_payload("greenhouse", "gone", None).status is BoardStatus.DEAD

    def test_a_board_answering_with_the_wrong_shape_is_dead(self):
        assert classify_payload("greenhouse", "odd", {"unexpected": 1}).status is BoardStatus.EMPTY
        assert classify_payload("lever", "odd", {"not": "a list"}).status is BoardStatus.DEAD

    def test_an_ats_with_no_parser_is_dead(self):
        assert classify_payload("workday", "bigco", {"jobs": []}).status is BoardStatus.DEAD

    def test_the_region_flag_uses_the_pipeline_rules(self):
        # The recon script had its own European city list, which is how the
        # seed's idea of "has EU" drifted from the dashboard's.
        payload = {"jobs": [{"id": 1, "title": "Engineer", "location": {"name": "Berlin, Germany"}}]}
        assert classify_payload("greenhouse", "acme", payload).has_eu

    def test_a_us_only_board_is_not_flagged_eu(self):
        payload = {"jobs": [{"id": 1, "title": "Engineer", "location": {"name": "Austin, TX"}}]}
        assert not classify_payload("greenhouse", "acme", payload).has_eu


class TestProbe:
    def test_it_reaches_the_board_through_the_real_transport(self):
        from etl.sources.discovery import probe_board

        client, handler = board_client(
            {"acme": RecordedBoard(payload=load_fixture("greenhouse.json"))}
        )
        probe = probe_board(client, "greenhouse", "acme", RecordingSleeper())
        assert probe.is_usable
        assert handler.call_count == 1

    def test_an_unknown_ats_is_not_requested_at_all(self):
        from etl.sources.discovery import probe_board

        client, handler = board_client({})
        assert probe_board(client, "workday", "acme", RecordingSleeper()).status is BoardStatus.DEAD
        assert handler.call_count == 0


class TestDedupe:
    def test_a_company_on_two_boards_keeps_the_one_with_postings(self):
        # Mid-migration companies answer on both, usually with the old one
        # empty. Seeding both crawls a dead board every day forever.
        probes = [
            Probe("greenhouse", "acme", BoardStatus.EMPTY),
            Probe("lever", "acme", BoardStatus.ACTIVE, n_jobs=42),
        ]
        assert dedupe_candidates(probes) == [probes[1]]

    def test_between_two_active_boards_the_fuller_one_wins(self):
        probes = [
            Probe("greenhouse", "acme", BoardStatus.ACTIVE, n_jobs=3),
            Probe("lever", "acme", BoardStatus.ACTIVE, n_jobs=40),
        ]
        assert dedupe_candidates(probes)[0].source == "lever"

    def test_a_dead_board_loses_to_an_empty_one(self):
        probes = [
            Probe("greenhouse", "acme", BoardStatus.DEAD),
            Probe("lever", "acme", BoardStatus.EMPTY),
        ]
        assert dedupe_candidates(probes)[0].status is BoardStatus.EMPTY

    def test_different_companies_all_survive(self):
        probes = [
            Probe("greenhouse", "acme", BoardStatus.ACTIVE, n_jobs=1),
            Probe("lever", "other", BoardStatus.ACTIVE, n_jobs=1),
        ]
        assert len(dedupe_candidates(probes)) == 2

    def test_the_order_is_stable(self):
        probes = [
            Probe("lever", "zeta", BoardStatus.ACTIVE, n_jobs=1),
            Probe("greenhouse", "alpha", BoardStatus.ACTIVE, n_jobs=1),
        ]
        assert [p.slug for p in dedupe_candidates(probes)] == ["alpha", "zeta"]


def test_a_probe_renders_as_a_seed_entry():
    entry = Probe("lever", "acme", BoardStatus.ACTIVE, n_jobs=9, has_eu=True).as_seed_entry(
        name="Acme", added="2026-08-19"
    )
    assert entry["ats"] == "lever"
    assert entry["status"] == "active"
    assert entry["added"] == "2026-08-19"
