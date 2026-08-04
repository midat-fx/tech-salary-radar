"""Which currency a figure is in, and how much that answer is worth."""

from __future__ import annotations

import pytest

from etl.money import (
    AMBIGUOUS_SYMBOLS,
    SUPPORTED,
    SYMBOL_TO_CURRENCY,
    Confidence,
    from_code,
    from_symbol,
    normalise_code,
)


class TestNormalise:
    @pytest.mark.parametrize("raw,expected", [("gbp", "GBP"), ("  eur ", "EUR"), ("USD", "USD")])
    def test_it_upper_cases_and_trims(self, raw, expected):
        assert normalise_code(raw) == expected

    def test_nothing_readable_is_none(self):
        assert normalise_code(None) is None
        assert normalise_code("   ") is None


class TestFromCode:
    def test_a_structured_field_is_the_strongest_signal(self):
        guess = from_code("GBP")
        assert guess.code == "GBP"
        assert guess.confidence is Confidence.DECLARED
        assert guess.is_certain

    def test_a_code_found_in_text_is_slightly_weaker_but_still_certain(self):
        guess = from_code("EUR", declared=False)
        assert guess.confidence is Confidence.CODE_IN_TEXT
        assert guess.is_certain

    def test_no_code_falls_back_to_an_assumed_usd(self):
        guess = from_code(None)
        assert guess.code == "USD"
        assert guess.confidence is Confidence.ASSUMED
        assert not guess.is_certain


class TestFromSymbol:
    def test_pound_and_euro_identify_one_currency_each(self):
        assert from_symbol("£").code == "GBP"
        assert from_symbol("€").code == "EUR"
        assert from_symbol("£").confidence is Confidence.SYMBOL

    def test_a_dollar_sign_resolves_to_usd_but_only_as_an_assumption(self):
        # $ is CAD, AUD, NZD, SGD, HKD and more. On a US-centric board set it is
        # usually USD, and reading a Canadian range as USD moves it by a quarter
        # — so the guess is recorded rather than baked in.
        guess = from_symbol("$")
        assert guess.code == "USD"
        assert guess.confidence is Confidence.ASSUMED

    def test_an_unknown_symbol_does_not_crash_the_parse(self):
        assert from_symbol("₸").code == "USD"
        assert from_symbol(None).confidence is Confidence.ASSUMED


class TestVocabulary:
    def test_the_supported_set_is_what_the_fx_cascade_provides(self):
        assert set(SUPPORTED) == {"USD", "GBP", "EUR"}

    def test_every_unambiguous_symbol_maps_into_the_supported_set(self):
        assert set(SYMBOL_TO_CURRENCY.values()) <= set(SUPPORTED)

    def test_the_ambiguous_symbols_are_not_in_the_unambiguous_map(self):
        assert not (AMBIGUOUS_SYMBOLS & set(SYMBOL_TO_CURRENCY))

    def test_support_is_a_property_of_the_guess(self):
        assert from_code("GBP").is_supported
        assert not from_code("JPY").is_supported
