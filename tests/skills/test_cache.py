"""What has already been labelled, and by which generation of the prompt."""

from __future__ import annotations

from etl.normalize import write_partition
from etl.skills import processed_uids, read_cache_state

DAY = "2026-08-20"


def label(uid, skill="Python", version="v1"):
    return {
        "job_uid": uid,
        "skill": skill,
        "source": "llm",
        "prompt_version": version,
        "extracted_at": "2026-08-20T00:00:00Z",
    }


class TestEmpty:
    def test_no_cache_yet_is_not_an_error(self, tmp_path):
        state = read_cache_state(str(tmp_path))
        assert state.current == frozenset()
        assert state.stale == frozenset()
        assert processed_uids(str(tmp_path)) == set()


class TestSplit:
    def test_labels_from_an_older_prompt_are_stale_and_re_extractable(self, tmp_path):
        write_partition(
            [label("ashby:c:a", version="v1"), label("ashby:c:b", "Go", version="v2")],
            tmp_path,
            "skills",
            DAY,
        )
        state = read_cache_state(str(tmp_path), prompt_version="v2")
        assert state.current == {"ashby:c:b"}
        assert state.stale == {"ashby:c:a"}

    def test_processed_is_the_union_the_extractor_skips(self, tmp_path):
        write_partition(
            [label("ashby:c:a", version="v1"), label("ashby:c:b", "Go", version="v2")],
            tmp_path,
            "skills",
            DAY,
        )
        state = read_cache_state(str(tmp_path), prompt_version="v2")
        assert state.processed == {"ashby:c:a", "ashby:c:b"}

    def test_a_posting_with_a_current_label_is_not_stale(self, tmp_path):
        # Re-extracting it would spend budget to produce a row that changes
        # nothing: the aggregator already resolves which generation wins.
        write_partition(
            [label("ashby:c:a", version="v1"), label("ashby:c:a", "Go", version="v2")],
            tmp_path,
            "skills",
            DAY,
        )
        state = read_cache_state(str(tmp_path), prompt_version="v2")
        assert state.current == {"ashby:c:a"}
        assert state.stale == frozenset()

    def test_a_processed_but_empty_posting_still_counts_as_labelled(self, tmp_path):
        # The null row is the whole point: "labelled, found nothing" must not be
        # queued again forever.
        write_partition([label("ashby:c:a", skill=None)], tmp_path, "skills", DAY)
        assert read_cache_state(str(tmp_path)).current == {"ashby:c:a"}

    def test_the_description_reports_both_halves(self, tmp_path):
        write_partition([label("ashby:c:a")], tmp_path, "skills", DAY)
        assert "1 current" in read_cache_state(str(tmp_path)).describe()
