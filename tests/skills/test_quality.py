"""The evaluation set, and the two scores that fail in opposite directions."""

from __future__ import annotations

from etl.skills import Score, lint_labels, score_labels


def example(eid="1", text="We use Python", expected=None):
    return {"id": eid, "text": text, "expected": ["Python"] if expected is None else expected}


class TestLint:
    def test_a_clean_set_has_no_issues(self):
        assert lint_labels([example()]) == []

    def test_a_label_outside_the_catalog_is_flagged(self):
        # A typo in an expected label makes the model look wrong forever on a
        # skill it gets right, and the obvious response is to change the prompt.
        issues = lint_labels([example(expected=["Pythonn"])])
        assert len(issues) == 1
        assert "Pythonn" in str(issues[0])

    def test_a_known_alias_is_still_flagged_but_with_the_canonical_name(self):
        issues = lint_labels([example(expected=["python3"])])
        assert "did you mean 'Python'" in str(issues[0])

    def test_a_duplicate_id_is_flagged(self):
        assert any("duplicate id" in str(i) for i in lint_labels([example(), example()]))

    def test_an_empty_text_is_flagged(self):
        assert any("empty text" in str(i) for i in lint_labels([example(text="   ")]))

    def test_repeated_expected_labels_are_flagged(self):
        assert any("repeat" in str(i) for i in lint_labels([example(expected=["Python", "Python"])]))

    def test_a_missing_expected_key_is_flagged_once(self):
        issues = lint_labels([{"id": "1", "text": "x"}])
        assert [i.problem for i in issues] == ["no expected labels"]


class TestScore:
    def test_a_perfect_run(self):
        score = score_labels({"1": ["Python", "SQL"]}, {"1": ["Python", "SQL"]})
        assert score.precision == 1.0 and score.recall == 1.0 and score.f1 == 1.0

    def test_a_claimed_skill_that_is_not_there_costs_precision(self):
        # Low precision inflates a premium: postings land in the with-pool that
        # do not belong there.
        score = score_labels({"1": ["Python"]}, {"1": ["Python", "Go"]})
        assert score.precision == 0.5
        assert score.recall == 1.0

    def test_a_missed_skill_costs_recall(self):
        score = score_labels({"1": ["Python", "Go"]}, {"1": ["Python"]})
        assert score.recall == 0.5
        assert score.precision == 1.0

    def test_a_posting_the_model_dropped_counts_every_label_as_missed(self):
        # A model that answers nothing must not score perfectly on precision.
        score = score_labels({"1": ["Python"], "2": ["Go"]}, {"1": ["Python"]})
        assert score.recall == 0.5
        assert score.false_negative == 1

    def test_an_empty_expectation_is_satisfied_by_an_empty_answer(self):
        # Nothing claimed and nothing missed: both ratios are vacuously perfect,
        # which is why a set of empty examples cannot vouch for a prompt.
        score = score_labels({"1": []}, {"1": []})
        assert (score.precision, score.recall, score.f1) == (1.0, 1.0, 1.0)
        assert (score.true_positive, score.false_positive, score.false_negative) == (0, 0, 0)

    def test_the_description_carries_the_counts_behind_the_ratios(self):
        line = Score(3, 1, 2).describe()
        assert "tp 3" in line and "fp 1" in line and "fn 2" in line
