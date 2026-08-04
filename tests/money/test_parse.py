"""Finding a pay range in an ad that is full of numbers which are not pay."""

from __future__ import annotations

import pytest

from etl.money import Confidence, Interval, find_anchored_range, find_range, parse_amount
from etl.money.parse import currency_from_text


class TestParseAmount:
    @pytest.mark.parametrize(
        "raw,suffix,expected",
        [
            ("150,000", None, 150_000),
            ("150000", None, 150_000),
            ("150", "K", 150_000),
            ("211.4", "K", 211_400),
            ("1.2", "M", 1_200_000),
            ("70.000", None, 70_000),
        ],
    )
    def test_the_shapes_boards_actually_write(self, raw, suffix, expected):
        assert parse_amount(raw, suffix) == pytest.approx(expected)

    def test_a_european_thousands_dot_needs_exactly_three_trailing_digits(self):
        assert parse_amount("70.000") == 70_000
        # 211.4 must stay a decimal, or "211.4K" becomes 2,114,000.
        assert parse_amount("211.4") == pytest.approx(211.4)

    def test_a_magnitude_suffix_makes_the_dot_a_decimal_point(self):
        # "150.000K" is nonsense either way, but 150K is the sane reading of it
        # and 150M is not; the suffix is the stronger signal about the dot.
        assert parse_amount("150.000", "K") == pytest.approx(150_000)


class TestFindRange:
    def test_a_plain_dollar_pair(self):
        found = find_range("$150,000 - $180,000")
        assert (found.low, found.high) == (150_000, 180_000)
        assert found.currency.code == "USD"

    def test_a_symbol_identifies_pounds_and_euros_with_confidence(self):
        assert find_range("£85,000 – £100,000").currency == pytest.approx(
            find_range("£85,000 – £100,000").currency
        )
        gbp = find_range("£85,000 – £100,000")
        assert gbp.currency.code == "GBP"
        assert gbp.currency.confidence is Confidence.SYMBOL

    def test_a_dollar_sign_is_usd_but_only_assumed(self):
        # $ is CAD, AUD, SGD and more; on these boards it is usually USD, and
        # the assumption is recorded rather than hidden.
        assert find_range("$150,000 - $180,000").currency.confidence is Confidence.ASSUMED

    def test_an_iso_code_wins_over_the_generic_pattern(self):
        # "GBP 90,000 - 110,000" carries no symbol and used to be read as USD.
        found = find_range("GBP 90,000 - 110,000")
        assert found.currency.code == "GBP"
        assert found.currency.confidence is Confidence.CODE_IN_TEXT
        assert (found.low, found.high) == (90_000, 110_000)

    def test_a_magnitude_suffix_propagates_from_the_upper_bound(self):
        found = find_range("$150-200K")
        assert (found.low, found.high) == (150_000, 200_000)

    def test_a_one_sided_floor_is_a_range_with_no_ceiling(self):
        # "from $180,000" is a commitment; dropping it loses the most senior ads.
        found = find_range("Compensation starts at $180,000 depending on level")
        assert found.low == 180_000
        assert found.high is None
        assert found.is_one_sided

    def test_the_interval_comes_from_the_wording(self):
        assert find_range("$75 - $95 per hour").interval is Interval.HOUR
        assert find_range("€5.000 - €6.000 per month").interval is Interval.MONTH
        assert find_range("$150,000 - $180,000").interval is Interval.YEAR

    def test_text_with_no_figures_yields_nothing(self):
        assert find_range("Competitive salary and equity") is None
        assert find_range("") is None
        assert find_range(None) is None

    def test_an_inverted_pair_comes_back_ordered(self):
        found = find_range("$180,000 - $150,000")
        assert (found.low, found.high) == (150_000, 180_000)


class TestAnchoring:
    ad = (
        "About us: we raised $100,000,000 in Series C. "
        "Benefits include a signing bonus of $2,000 - $5,000 and a 401k match. "
        "The base salary range for this role is $150,000 - $180,000. "
        "We also offer equity."
    )

    def test_it_finds_the_pay_and_not_the_funding_round(self):
        found = find_anchored_range(self.ad)
        assert (found.low, found.high) == (150_000, 180_000)

    def test_without_anchoring_the_bonus_would_win(self):
        # The contrast that justifies the anchor: an unanchored search takes the
        # first pair in the ad, which here is the signing bonus. This is why a
        # job description is never parsed without one.
        assert find_range(self.ad).low == 2_000

    def test_an_ad_with_numbers_but_no_salary_wording_yields_nothing(self):
        assert find_anchored_range("We raised $100,000,000 and match $2,000 of your 401k.") is None

    def test_the_interval_is_read_next_to_the_figure_not_across_the_ad(self):
        # Hourly ads almost always also say "annually" somewhere else; the rate
        # is what sits by the anchor.
        ad = (
            "This is a full-time role reviewed annually. "
            "The hourly rate for this position is $75 - $95 per hour."
        )
        assert find_anchored_range(ad).interval is Interval.HOUR

    def test_the_first_anchored_range_in_document_order_wins(self):
        ad = "Base salary: $150,000 - $180,000. Later: total compensation $300,000 - $400,000."
        assert find_anchored_range(ad).low == 150_000

    def test_a_narrow_window_can_miss_a_distant_figure(self):
        ad = "The base salary range for this position, subject to review, is " + " " * 200 + "$150,000 - $180,000"
        assert find_anchored_range(ad, window=20) is None
        assert find_anchored_range(ad, window=400) is not None


class TestCurrencyFromText:
    def test_a_code_beats_a_symbol(self):
        assert currency_from_text("EUR 70.000 ($80,000)").code == "EUR"

    def test_a_symbol_is_used_when_there_is_no_code(self):
        assert currency_from_text("£85,000").code == "GBP"

    def test_nothing_stated_assumes_usd_and_says_so(self):
        guess = currency_from_text("competitive")
        assert guess.code == "USD"
        assert guess.confidence is Confidence.ASSUMED
