"""The hand-edited file that decides whether a prompt change is an improvement."""

from __future__ import annotations

import json

import pytest

from etl.skills.evalset import EvalExample, read_evalset, write_evalset


def line(**over):
    item = {"id": "1", "title": "Backend Engineer", "text": "We use Python", "expected": ["Python"]}
    item.update(over)
    return json.dumps(item, ensure_ascii=False)


class TestRead:
    def test_it_parses_one_example_per_line(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(line() + "\n" + line(id="2") + "\n")
        parsed = read_evalset(path)
        assert len(parsed) == 2
        assert parsed.examples[0].expected == ("Python",)

    def test_blank_lines_are_ignored(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(line() + "\n\n\n")
        assert len(read_evalset(path)) == 1

    def test_a_malformed_line_raises_with_its_number(self, tmp_path):
        # A set that silently shrinks is a set whose score means something
        # different from last week's, and the score is compared in CI.
        path = tmp_path / "eval.jsonl"
        path.write_text(line() + "\n{not json\n")
        with pytest.raises(ValueError, match=":2:"):
            read_evalset(path)

    def test_the_linter_runs_on_the_way_in(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(line(expected=["Pythonn"]) + "\n")
        parsed = read_evalset(path)
        assert not parsed.is_clean
        assert "Pythonn" in parsed.issues[0]

    def test_a_clean_set_says_so(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(line() + "\n")
        parsed = read_evalset(path)
        assert parsed.is_clean
        assert "1 examples, 0 issues" in parsed.describe()

    def test_it_offers_the_shape_the_extractor_consumes(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(line() + "\n")
        posting = read_evalset(path).examples[0].as_posting(0)
        assert set(posting) == {"id", "title", "text"}


class TestWrite:
    def test_it_round_trips(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        examples = [EvalExample("1", "Dev", "We use Go", ("Go",))]
        write_evalset(examples, path)
        assert read_evalset(path).examples[0].expected == ("Go",)

    def test_one_line_per_example_keeps_a_review_diff_small(self, tmp_path):
        # A pretty-printed array turns a one-label change into a twelve-line diff.
        path = tmp_path / "eval.jsonl"
        write_evalset([EvalExample(str(i), "t", "x", ("Go",)) for i in range(3)], path)
        assert len(path.read_text().strip().splitlines()) == 3

    def test_an_empty_set_writes_an_empty_file(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        write_evalset([], path)
        assert path.read_text() == ""

    def test_non_ascii_stays_readable(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        write_evalset([EvalExample("1", "Разработчик", "питон", ("Python",))], path)
        assert "Разработчик" in path.read_text()


def test_the_committed_eval_set_is_clean():
    # The real file, checked as data: a typo in it makes the model look wrong
    # forever on a skill it gets right.
    parsed = read_evalset()
    assert len(parsed) >= 20
    assert parsed.issues == ()
