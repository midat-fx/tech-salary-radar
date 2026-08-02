"""The two doors: what they promise the rest of the package."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from etl.clock import (
    SystemClock,
    SystemSleeper,
    age_in_days,
    iso_day,
    iso_second,
    parse_iso,
    plus_days,
)
from etl.rng import BOOTSTRAP_SEED, Jitter, SeededRng, bootstrap_rng

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 7, 48, 11, 123456, tzinfo=UTC)


class TestIsoFormatting:
    def test_iso_day_is_the_partition_form(self):
        assert iso_day(NOW) == "2026-08-19"

    def test_iso_second_drops_microseconds_and_uses_z(self):
        # Two runs over identical data must produce identical bytes; microseconds
        # would differ for no reader's benefit.
        assert iso_second(NOW) == "2026-08-19T07:48:11Z"

    def test_iso_second_converts_to_utc_first(self):
        moscow = NOW.astimezone(timezone(timedelta(hours=3)))
        assert iso_second(moscow) == "2026-08-19T07:48:11Z"


class TestParseIso:
    @pytest.mark.parametrize(
        "raw",
        ["2026-08-19T07:48:11Z", "2026-08-19T07:48:11+00:00", "  2026-08-19T07:48:11Z  "],
    )
    def test_accepts_the_forms_boards_actually_send(self, raw):
        assert parse_iso(raw) == datetime(2026, 8, 19, 7, 48, 11, tzinfo=UTC)

    def test_a_naive_stamp_is_read_as_utc(self):
        assert parse_iso("2026-08-19T07:48:11") == datetime(2026, 8, 19, 7, 48, 11, tzinfo=UTC)

    @pytest.mark.parametrize("raw", [None, "", "   ", "not a date", "2026-13-45"])
    def test_an_unreadable_stamp_is_absent_not_fatal(self, raw):
        # A board sending junk must cost one field, not the whole crawl.
        assert parse_iso(raw) is None


class TestAgeInDays:
    def test_counts_whole_days_between_calendar_dates(self):
        assert age_in_days("2026-08-16T23:59:00Z", NOW) == 3
        assert age_in_days("2026-08-19T00:00:01Z", NOW) == 0

    def test_accepts_date_and_datetime_as_well_as_text(self):
        assert age_in_days(date(2026, 8, 17), NOW) == 2
        assert age_in_days(datetime(2026, 8, 17, tzinfo=UTC), NOW) == 2

    def test_a_future_stamp_is_negative_not_clamped(self):
        # A board reporting tomorrow is a data problem the caller should see.
        assert age_in_days("2026-08-21T00:00:00Z", NOW) == -2

    def test_unreadable_input_has_no_age(self):
        assert age_in_days(None, NOW) is None
        assert age_in_days("whenever", NOW) is None


class TestSystemClock:
    def test_now_is_aware_and_utc(self):
        moment = SystemClock().now()
        assert moment.tzinfo is not None
        assert moment.utcoffset().total_seconds() == 0

    def test_today_answers_in_the_requested_zone(self):
        clock = SystemClock()
        # Kiritimati is UTC+14 and Niue UTC-11: 25 hours apart, so the pair can
        # never both equal the UTC date, which is exactly why the zone is a parameter.
        assert clock.today("Pacific/Kiritimati") >= clock.today("Pacific/Niue")


class TestSystemSleeper:
    def test_records_what_it_waited_for(self):
        sleeper = SystemSleeper()
        sleeper.sleep(0.001)
        sleeper.sleep(0.001)
        assert sleeper.total_seconds == pytest.approx(0.002)

    def test_a_zero_or_negative_pause_is_not_a_pause(self):
        sleeper = SystemSleeper()
        sleeper.sleep(0)
        sleeper.sleep(-5)
        assert sleeper.total_seconds == 0.0


class TestSeededRng:
    def test_the_same_seed_gives_the_same_sequence(self):
        first = [SeededRng(7).uniform(0, 1) for _ in range(3)]
        second = [SeededRng(7).uniform(0, 1) for _ in range(3)]
        assert first == second

    def test_different_seeds_diverge(self):
        assert SeededRng(1).uniform(0, 1) != SeededRng(2).uniform(0, 1)

    def test_reset_rewinds_so_two_aggregations_in_one_process_match(self):
        rng = SeededRng(11)
        first = rng.choices([1, 2, 3, 4, 5], k=5)
        rng.reset()
        assert rng.choices([1, 2, 3, 4, 5], k=5) == first

    def test_choices_draws_with_replacement(self):
        drawn = SeededRng(3).choices([9], k=4)
        assert drawn == [9, 9, 9, 9]

    def test_the_published_interval_is_drawn_from_a_pinned_seed(self):
        # Changing this seed moves every confidence interval the site shows,
        # so it is a versioned decision rather than a tunable.
        assert bootstrap_rng().seed == BOOTSTRAP_SEED == 20260719


class TestJitter:
    def test_a_pause_stays_inside_the_declared_spread(self):
        jitter = Jitter(base_seconds=0.5, rng=SeededRng(1))
        for _ in range(50):
            assert 0.7 <= jitter.next_pause() <= 0.9

    def test_the_schedule_is_reproducible_for_a_given_seed(self):
        a = [Jitter(base_seconds=0.5, rng=SeededRng(4)).next_pause() for _ in range(3)]
        b = [Jitter(base_seconds=0.5, rng=SeededRng(4)).next_pause() for _ in range(3)]
        assert a == b

    def test_a_zero_base_still_never_returns_a_negative_pause(self):
        jitter = Jitter(base_seconds=0.0, spread_low=-5, spread_high=-1, rng=SeededRng(2))
        assert jitter.next_pause() == 0.0

    def test_an_inverted_spread_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="spread_low"):
            Jitter(base_seconds=1.0, spread_low=0.9, spread_high=0.1)


def test_plus_days_keeps_the_timezone():
    assert plus_days(NOW, 3) == datetime(2026, 8, 22, 7, 48, 11, 123456, tzinfo=UTC)
