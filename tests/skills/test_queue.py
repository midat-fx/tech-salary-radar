"""Who gets the day's labelling budget. Getting this wrong is invisible:
coverage still rises, just on the postings that matter least."""

from __future__ import annotations

from etl.skills import Candidate, prioritise


def cand(uid, source="ashby", salary=False, published="", stale=False):
    return Candidate(uid, {"source": source, "company": "c"}, salary, published, stale)


class TestOrder:
    def test_salary_bearing_postings_go_first(self):
        # The skill premium can only use postings that have a salary; a labelled
        # posting without one contributes to coverage and to nothing else.
        queue = [cand("a"), cand("b", salary=True)]
        assert [c.uid for c in prioritise(queue)] == ["b", "a"]

    def test_newest_first_among_equals(self):
        queue = [
            cand("old", salary=True, published="2026-01-01T00:00:00Z"),
            cand("new", salary=True, published="2026-07-19T00:00:00Z"),
        ]
        assert [c.uid for c in prioritise(queue)][0] == "new"

    def test_never_labelled_beats_re_extraction(self):
        # A prompt upgrade must not stall coverage of fresh postings while it
        # redoes old ones.
        queue = [cand("stale", salary=True, stale=True), cand("fresh")]
        assert [c.uid for c in prioritise(queue)] == ["fresh", "stale"]

    def test_stale_wins_over_nothing(self):
        assert [c.uid for c in prioritise([cand("stale", stale=True)])] == ["stale"]


class TestInterleaving:
    def test_one_board_cannot_take_the_whole_budget(self):
        # Greenhouse is two thirds of the crawl; without this it takes two
        # thirds of the budget and the other boards are never labelled.
        queue = [cand("g1", "greenhouse"), cand("g2", "greenhouse"), cand("a1", "ashby")]
        picked = [c.uid for c in prioritise(queue, limit=2)]
        assert {u[0] for u in picked} == {"g", "a"}

    def test_interleaving_preserves_priority_inside_a_source(self):
        queue = [
            cand("g_plain", "greenhouse"),
            cand("g_salary", "greenhouse", salary=True),
            cand("a1", "ashby"),
        ]
        picked = [c.uid for c in prioritise(queue)]
        assert picked.index("g_salary") < picked.index("g_plain")

    def test_a_single_source_is_simply_ordered(self):
        queue = [cand("a"), cand("b", salary=True)]
        assert [c.uid for c in prioritise(queue)] == ["b", "a"]


class TestBudget:
    def test_the_limit_cuts_the_tail(self):
        queue = [cand(str(i)) for i in range(10)]
        assert len(prioritise(queue, limit=3)) == 3

    def test_no_limit_returns_everything(self):
        queue = [cand(str(i)) for i in range(10)]
        assert len(prioritise(queue)) == 10

    def test_a_limit_beyond_the_queue_is_harmless(self):
        assert len(prioritise([cand("a")], limit=99)) == 1

    def test_an_empty_queue_is_an_empty_result(self):
        assert prioritise([], limit=5) == []
