"""The crawl's only input: what counts as a usable board, and what is dropped."""

from __future__ import annotations

import json

from etl.sources import load_seed, validate_seed


def entry(**over):
    base = {"ats": "greenhouse", "slug": "acme", "name": "Acme", "status": "active"}
    base.update(over)
    return base


class TestValidation:
    def test_an_active_entry_survives(self):
        report = validate_seed([entry()])
        assert report.usable == 1
        assert report.entries[0].source == "greenhouse"
        assert report.entries[0].slug == "acme"

    def test_both_spellings_of_the_ats_field_are_accepted(self):
        # The recon script wrote "ats"; entries added by hand used "source".
        assert validate_seed([entry(ats=None, source="lever")]).usable == 1
        assert validate_seed([entry()]).entries[0].source == "greenhouse"

    def test_inactive_boards_are_skipped_and_counted(self):
        # The recon script marks a board inactive when it 404s; re-checking it
        # daily spends one request per board for no rows.
        report = validate_seed([entry(), entry(slug="dead", status="inactive")])
        assert report.usable == 1
        assert report.inactive == 1

    def test_an_ats_with_no_adapter_is_dropped_by_name(self):
        report = validate_seed([entry(ats="workday", slug="bigco")])
        assert report.usable == 0
        assert report.unknown_source == ("workday:bigco",)

    def test_the_same_board_twice_is_counted_once(self):
        # A duplicate is the same company counted twice in "companies tracked".
        report = validate_seed([entry(), entry()])
        assert report.usable == 1
        assert report.duplicates == ("greenhouse:acme",)

    def test_the_same_slug_on_two_boards_is_two_boards(self):
        report = validate_seed([entry(), entry(ats="lever")])
        assert report.usable == 2

    def test_an_entry_with_no_slug_is_malformed(self):
        report = validate_seed([entry(slug=None), entry(slug=123)])
        assert report.usable == 0
        assert len(report.malformed) == 2

    def test_a_non_dict_entry_does_not_crash_the_loader(self):
        report = validate_seed(["greenhouse/acme", entry()])
        assert report.usable == 1
        assert len(report.malformed) == 1

    def test_a_missing_name_falls_back_to_the_slug(self):
        assert validate_seed([entry(name=None)]).entries[0].name == "acme"


class TestReport:
    def test_the_description_names_every_reason_for_a_drop(self):
        report = validate_seed(
            [entry(), entry(status="x"), entry(ats="workday", slug="w"), entry(), entry(slug=None)]
        )
        line = report.describe()
        assert "1 boards" in line
        assert "1 inactive" in line
        assert "1 unknown-ats" in line
        assert "1 duplicate" in line
        assert "1 malformed" in line


class TestLoad:
    def test_it_produces_the_dict_shape_the_crawl_consumes(self, tmp_path):
        path = tmp_path / "seed.json"
        path.write_text(json.dumps([entry(), entry(slug="dead", status="inactive")]))
        loaded = load_seed(path)
        assert loaded == [{"source": "greenhouse", "slug": "acme", "name": "Acme"}]

    def test_the_committed_seed_file_is_usable(self):
        # The real file, checked as data: a broken seed is a crawl that returns
        # nothing and a volume guard that refuses the day.
        report = validate_seed(json.loads(__import__("pathlib").Path("data/seed_companies.json").read_text()))
        assert report.usable > 200
        assert report.malformed == ()
        assert report.duplicates == ()
