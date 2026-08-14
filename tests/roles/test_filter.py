"""What belongs in the salary statistics, and why the checks run in this order."""

from __future__ import annotations

import pytest

from etl.roles import Decision, classify_role, passes_role_filter


class TestAllowed:
    @pytest.mark.parametrize(
        "title",
        [
            "Senior Backend Engineer",
            "Staff Software Engineer",
            "Data Scientist",
            "Site Reliability Engineer",
            "iOS Developer",
            "Machine Learning Engineer",
            "SDET",
            "Security Engineer",
            "Member of Technical Staff",
        ],
    )
    def test_technical_titles_pass(self, title):
        assert passes_role_filter(title)


class TestHardDeny:
    @pytest.mark.parametrize(
        "title",
        [
            "Product Manager",
            "Technical Program Manager",
            "Solutions Engineer",
            "Sales Engineer",
            "Product Designer",
            "Account Executive",
        ],
    )
    def test_engineering_adjacent_roles_are_refused(self, title):
        # These contain tech words and are sales and project work; nothing
        # rescues a hard deny.
        assert not passes_role_filter(title)
        assert classify_role(title).decision is Decision.HARD_DENIED

    def test_a_tech_department_does_not_rescue_a_hard_deny(self):
        assert not passes_role_filter("Product Manager", department="Engineering")

    def test_data_annotation_gig_work_is_refused(self):
        # It advertises around $29k against a $221k IC median and dragged the
        # junior bucket down by a third.
        assert not passes_role_filter("Data Annotation Specialist")
        assert not passes_role_filter("Image Labeler")


class TestSoftDeny:
    def test_a_non_technical_function_is_dropped(self):
        assert not passes_role_filter("Marketing Manager")
        assert classify_role("Marketing Manager").decision is Decision.SOFT_DENIED

    def test_an_allow_signal_beats_a_soft_deny(self):
        # "Data Engineer, Marketing Analytics" is an engineering job in a
        # marketing team; reading the soft deny first would drop it.
        assert passes_role_filter("Data Engineer, Marketing Analytics")
        assert classify_role("Data Engineer, Marketing Analytics").decision is (
            Decision.ALLOWED_BY_TITLE
        )

    def test_support_is_denied_but_platform_support_engineering_is_not(self):
        assert not passes_role_filter("Customer Support Specialist")
        assert passes_role_filter("Support Engineer, Platform")


class TestDepartment:
    def test_a_tech_department_rescues_a_silent_title(self):
        verdict = classify_role("Analyst", department="Data Platform")
        assert verdict.keep
        assert verdict.decision is Decision.ALLOWED_BY_DEPARTMENT

    def test_a_non_tech_department_does_not(self):
        assert not passes_role_filter("Analyst", department="Finance")

    def test_the_department_is_never_consulted_when_the_title_spoke(self):
        assert passes_role_filter("Backend Engineer", department="Finance")


class TestNoSignal:
    @pytest.mark.parametrize("title", ["Chief of Staff", "Associate", "", None])
    def test_an_unclassifiable_posting_is_dropped(self, title):
        # Admitting it mixes an unknown population into every median.
        assert not passes_role_filter(title)

    def test_the_reason_is_named_so_a_shift_is_visible(self):
        assert classify_role("Chief of Staff").decision is Decision.NO_SIGNAL
        assert classify_role("").decision is Decision.NO_SIGNAL


def test_the_verdict_is_truthy_like_the_boolean_it_replaced():
    assert classify_role("Backend Engineer")
    assert not classify_role("Product Manager")
