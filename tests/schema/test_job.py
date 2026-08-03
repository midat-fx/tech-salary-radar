"""The raw posting shape, and the identity every later stage joins on."""

from __future__ import annotations

import pytest

from etl.schema import (
    RAW_JOB_FIELDS,
    REQUIRED_RAW_FIELDS,
    SENIORITIES,
    SOURCES,
    InvariantViolated,
    RawJob,
    check_raw_job,
    job_uid,
    split_uid,
)
from etl.schema.fields import JOBS, SNAPSHOTS, table_for


def raw(**over):
    data = {
        "source": "greenhouse",
        "company": "acme",
        "job_id": "12345",
        "title": "Senior Backend Engineer",
        "location_raw": "Berlin, Germany",
        "is_remote": False,
        "employment_type": "FullTime",
        "published_at": "2026-08-01T00:00:00Z",
        "apply_url": "https://boards.greenhouse.io/acme/jobs/12345",
        "department": "Engineering",
        "description": "We use Python and Postgres.",
        "raw_compensation": None,
    }
    data.update(over)
    return data


class TestUid:
    def test_it_is_the_three_parts_joined(self):
        assert job_uid("lever", "acme", "abc") == "lever:acme:abc"

    def test_it_round_trips(self):
        assert split_uid(job_uid("ashby", "acme", "xyz")) == ("ashby", "acme", "xyz")

    def test_a_colon_inside_the_id_survives(self):
        # Ashby ids contain colons; splitting on every colon would attribute the
        # job to the wrong company.
        uid = job_uid("ashby", "acme", "a:b:c")
        assert split_uid(uid) == ("ashby", "acme", "a:b:c")

    def test_a_malformed_uid_is_refused(self):
        with pytest.raises(InvariantViolated):
            split_uid("acme-12345")

    def test_the_same_posting_on_two_boards_gets_two_ids(self):
        # Which is exactly why cross-board de-duplication needs a different key.
        assert job_uid("lever", "acme", "1") != job_uid("greenhouse", "acme", "1")


class TestRawJob:
    def test_a_complete_posting_builds(self):
        job = RawJob.from_mapping(raw())
        assert job.uid == "greenhouse:acme:12345"
        assert job.title == "Senior Backend Engineer"

    def test_it_round_trips_through_the_dict_shape_the_pipeline_uses(self):
        job = RawJob.from_mapping(raw())
        assert RawJob.from_mapping(job.to_mapping()) == job
        assert set(job.to_mapping()) == set(RAW_JOB_FIELDS)

    @pytest.mark.parametrize("name", REQUIRED_RAW_FIELDS)
    def test_every_required_field_is_actually_required(self, name):
        with pytest.raises(InvariantViolated, match=name):
            RawJob.from_mapping(raw(**{name: None}))

    def test_a_blank_title_counts_as_missing(self):
        with pytest.raises(InvariantViolated, match="title"):
            RawJob.from_mapping(raw(title="   "))

    def test_an_unknown_source_is_refused(self):
        with pytest.raises(InvariantViolated, match="unknown source"):
            RawJob.from_mapping(raw(source="workday"))

    def test_an_unknown_field_is_refused(self):
        with pytest.raises(InvariantViolated, match="salary_text"):
            RawJob.from_mapping(raw(salary_text="$100k"))

    def test_optional_text_defaults_to_empty_not_none(self):
        job = RawJob.from_mapping(raw(location_raw=None, description=None))
        assert job.location_raw == ""
        assert job.description == ""

    def test_a_numeric_job_id_becomes_a_string(self):
        # Greenhouse sends ints, Lever sends strings; the uid must not depend on
        # which board a posting came from.
        assert RawJob.from_mapping(raw(job_id=12345)).uid.endswith(":12345")

    def test_it_is_frozen(self):
        job = RawJob.from_mapping(raw())
        with pytest.raises(Exception):
            job.title = "changed"  # type: ignore[misc]

    def test_check_accepts_a_bare_mapping_without_building(self):
        check_raw_job(raw())


class TestVocabularies:
    def test_the_three_sources_are_the_ones_with_adapters(self):
        assert set(SOURCES) == {"greenhouse", "lever", "ashby"}

    def test_unspecified_is_a_seniority_bucket_not_a_gap(self):
        # ADR 0006: L5 and IC3 land here rather than being guessed into a level.
        assert "unspecified" in SENIORITIES

    def test_stored_seniority_values_all_come_from_the_vocabulary(self):
        assert SNAPSHOTS.field("seniority").default in SENIORITIES
        assert JOBS.field("seniority").default in SENIORITIES

    def test_tables_are_addressable_by_their_storage_directory(self):
        assert table_for("snapshots") is SNAPSHOTS
        assert table_for("jobs") is JOBS
        with pytest.raises(KeyError, match="unknown table"):
            table_for("nope")

    def test_every_table_declares_its_key_and_sort_column(self):
        for name in ("snapshots", "jobs", "skills"):
            table = table_for(name)
            assert table.key, name
            assert table.sort_by in table.names, name
            for column in table.key:
                assert column in table.names, (name, column)

    def test_required_columns_are_a_subset_of_declared_ones(self):
        for table in (SNAPSHOTS, JOBS):
            assert set(table.required) <= set(table.names)
