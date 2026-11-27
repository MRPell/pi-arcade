"""Play hours and time limits (arcade-profiles M-2: AC-2, AC-3, AC-4, AC-7,
MH-2, DEC-1), decided over the shipped profiles and a ledger of plays."""

import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arcade_profiles import play  # noqa: E402
from arcade_profiles.profiles import ProfileError, load_profiles, parse_profiles  # noqa: E402
from arcade_profiles.rules import decide  # noqa: E402
from arcade_profiles.usage import Ledger  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), '..')
PROFILES = load_profiles(os.path.join(REPO, 'config', 'profiles.json'))
BY_ID = {p.id: p for p in PROFILES}

FRI_4PM = dt.datetime(2026, 11, 27, 16, 0)   # a school day, inside 3pm-8pm
FRI_10AM = dt.datetime(2026, 11, 27, 10, 0)  # a school day, before 3pm
SAT_10AM = dt.datetime(2026, 11, 28, 10, 0)


def ts(t):
    return t.timestamp()


def played(pid, start, minutes):
    return {'profile': pid, 'start': ts(start), 'seconds': minutes * 60.0}


def check(pid, now, plays=(), since=None, trusted=True):
    since = ts(now - dt.timedelta(days=30)) if since is None else since
    return decide(PROFILES, BY_ID[pid], now, list(plays), since, trusted)


def with_limits(pid, limits):
    raw = [{'id': p.id, 'name': p.name, 'role': p.role, 'combo': list(p.combo)} for p in PROFILES]
    shipped = {'hours': {'weekdays': '15:00-20:00', 'weekends': '09:00-20:00'},
               'time': {'minutes': 60, 'per': 'day'}}
    for r in raw:
        if r['role'] != 'owner':
            r['limits'] = limits if r['id'] == pid else shipped
    return parse_profiles({'profiles': raw})


class ShippedRulesTest(unittest.TestCase):
    def test_boys_get_an_hour_a_day_and_guest_half_an_hour(self):
        self.assertEqual(BY_ID['theo'].limits.minutes, 60)
        self.assertEqual(BY_ID['john'].limits.minutes, 60)
        self.assertEqual(BY_ID['guest'].limits.minutes, 30)
        self.assertIsNone(BY_ID['matt'].limits)

    def test_school_days_3_to_8_weekends_9_to_8(self):
        for pid in ('theo', 'john', 'guest'):
            hours = BY_ID[pid].limits.hours
            self.assertEqual(hours[4], [(15 * 60, 20 * 60)])   # Friday
            self.assertEqual(hours[5], [(9 * 60, 20 * 60)])    # Saturday


class HoursTest(unittest.TestCase):
    def test_ac2_outside_hours_refused_with_next_allowed(self):
        d = check('theo', FRI_10AM)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, 'hours')
        self.assertEqual(d.next_allowed, dt.datetime(2026, 11, 27, 15, 0))
        lines = play.reason_lines('Matt', d, FRI_10AM)
        self.assertIn('Next play: today at 3:00 pm', lines)

    def test_after_8pm_next_play_is_tomorrow_morning_on_a_weekend(self):
        now = dt.datetime(2026, 11, 27, 20, 30)
        d = check('john', now)
        self.assertEqual(d.reason, 'hours')
        self.assertEqual(d.next_allowed, dt.datetime(2026, 11, 28, 9, 0))
        self.assertIn('Next play: tomorrow at 9:00 am', play.reason_lines('Matt', d, now))

    def test_game_inside_hours_stops_when_hours_end(self):
        now = dt.datetime(2026, 11, 27, 19, 40)
        d = check('theo', now)
        self.assertTrue(d.allowed)
        self.assertEqual(d.until, dt.datetime(2026, 11, 27, 20, 0))

    def test_owner_plays_at_any_hour(self):
        d = check('matt', dt.datetime(2026, 11, 27, 3, 0))
        self.assertTrue(d.allowed)
        self.assertIsNone(d.until)


class TimeLimitTest(unittest.TestCase):
    def test_ac3_used_up_refused_and_says_so(self):
        d = check('theo', FRI_4PM, [played('theo', dt.datetime(2026, 11, 27, 15, 0), 60)])
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, 'used_up')
        self.assertEqual(play.TITLES[d.reason], 'Time is used up')
        self.assertEqual(d.next_allowed, dt.datetime(2026, 11, 28, 9, 0))

    def test_game_stops_when_time_left_runs_out(self):
        d = check('theo', FRI_4PM, [played('theo', dt.datetime(2026, 11, 27, 15, 0), 45)])
        self.assertTrue(d.allowed)
        self.assertEqual(d.until, FRI_4PM + dt.timedelta(minutes=15))

    def test_yesterdays_play_does_not_count_today(self):
        d = check('theo', SAT_10AM, [played('theo', dt.datetime(2026, 11, 27, 15, 0), 60)])
        self.assertTrue(d.allowed)
        self.assertEqual(d.until, SAT_10AM + dt.timedelta(minutes=60))

    def test_less_than_a_minute_left_counts_as_used_up(self):
        d = check('theo', FRI_4PM, [played('theo', dt.datetime(2026, 11, 27, 15, 0), 59.5)])
        self.assertEqual(d.reason, 'used_up')

    def test_ac4_each_profile_stops_at_its_own_limit_owner_never(self):
        start = dt.datetime(2026, 11, 28, 9, 0)
        plays = [played('theo', start, 60), played('john', start, 60)]
        later = dt.datetime(2026, 11, 28, 12, 0)
        self.assertEqual(check('theo', later, plays).reason, 'used_up')
        self.assertEqual(check('john', later, plays).reason, 'used_up')
        self.assertTrue(check('matt', later, plays + [played('matt', start, 600)]).allowed)
        guest_plays = [played('guest', start, 30)]
        self.assertEqual(check('guest', later, guest_plays).reason, 'used_up')
        self.assertTrue(check('guest', later, [played('guest', start, 10)]).allowed)

    def test_per_week(self):
        profiles = with_limits('theo', {'hours': {'weekdays': '15:00-20:00'},
                                        'time': {'minutes': 120, 'per': 'week'}})
        theo = next(p for p in profiles if p.id == 'theo')
        mon = dt.datetime(2026, 11, 23, 15, 0)
        plays = [played('theo', mon, 60), played('theo', mon + dt.timedelta(days=1), 60)]
        wed = dt.datetime(2026, 11, 25, 16, 0)
        d = decide(profiles, theo, wed, plays, ts(mon) - 1, True)
        self.assertEqual(d.reason, 'used_up')
        self.assertEqual(d.next_allowed, dt.datetime(2026, 11, 30, 15, 0))   # next Monday
        self.assertIn('this week', play.reason_lines('Matt', d, wed)[0])

    def test_per_several_days(self):
        profiles = with_limits('theo', {'hours': {'weekdays': '15:00-20:00', 'weekends': '09:00-20:00'},
                                        'time': {'minutes': 90, 'per': '3 days', 'from': '2026-11-25'}})
        theo = next(p for p in profiles if p.id == 'theo')
        plays = [played('theo', dt.datetime(2026, 11, 25, 15, 0), 90)]
        fri = dt.datetime(2026, 11, 27, 16, 0)        # day 3 of 25-27
        self.assertEqual(decide(profiles, theo, fri, plays, 0, True).reason, 'used_up')
        sat = dt.datetime(2026, 11, 28, 9, 30)        # a new 3-day stretch
        self.assertTrue(decide(profiles, theo, sat, plays, 0, True).allowed)

    def test_rollover_carries_unused_time_one_period(self):
        profiles = with_limits('theo', {'hours': {'weekdays': '15:00-20:00', 'weekends': '09:00-20:00'},
                                        'time': {'minutes': 60, 'per': 'day', 'rollover': True}})
        theo = next(p for p in profiles if p.id == 'theo')
        since = ts(dt.datetime(2026, 11, 20))
        thu = dt.datetime(2026, 11, 26, 15, 0)
        d = decide(profiles, theo, FRI_4PM, [played('theo', thu, 20)], since, True)
        self.assertEqual(d.until, FRI_4PM + dt.timedelta(minutes=60 + 40))
        # Nothing played Thursday: at most double.
        d = decide(profiles, theo, FRI_4PM, [], since, True)
        self.assertEqual(d.until, dt.datetime(2026, 11, 27, 18, 0))

    def test_no_rollover_from_before_counting_began(self):
        profiles = with_limits('theo', {'hours': {'weekdays': '15:00-20:00'},
                                        'time': {'minutes': 60, 'per': 'day', 'rollover': True}})
        theo = next(p for p in profiles if p.id == 'theo')
        d = decide(profiles, theo, FRI_4PM, [], ts(dt.datetime(2026, 11, 27, 12, 0)), True)
        self.assertEqual(d.until, FRI_4PM + dt.timedelta(minutes=60))


class GuestTest(unittest.TestCase):
    def test_ac7_mh2_guest_refused_while_a_player_is_used_up(self):
        plays = [played('theo', dt.datetime(2026, 11, 27, 15, 0), 60)]
        d = check('guest', FRI_4PM, plays)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, 'guest_blocked')
        self.assertEqual(d.blocker.id, 'theo')
        self.assertEqual(d.next_allowed, dt.datetime(2026, 11, 28, 9, 0))

    def test_guest_plays_when_no_player_is_used_up(self):
        plays = [played('theo', dt.datetime(2026, 11, 27, 15, 0), 30)]
        d = check('guest', FRI_4PM, plays)
        self.assertTrue(d.allowed)
        self.assertEqual(d.until, FRI_4PM + dt.timedelta(minutes=30))

    def test_owner_still_plays_while_a_player_is_used_up(self):
        plays = [played('theo', dt.datetime(2026, 11, 27, 15, 0), 60)]
        self.assertTrue(check('matt', FRI_4PM, plays).allowed)


class ClockTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_dec1_untrusted_clock_refuses_everyone_but_the_owner(self):
        for pid in ('theo', 'john', 'guest'):
            d = check(pid, FRI_4PM, trusted=False)
            self.assertFalse(d.allowed)
            self.assertEqual(d.reason, 'clock')
        self.assertTrue(check('matt', FRI_4PM, trusted=False).allowed)

    def test_clock_behind_the_last_play_is_not_trusted(self):
        ledger = Ledger(self.dir, wall_time=ts(FRI_4PM))
        ledger.start('theo', ts(FRI_4PM), 0.0)
        self.assertTrue(play.clock_trusted(True, ts(FRI_4PM) + 5, ledger))
        self.assertFalse(play.clock_trusted(True, ts(FRI_4PM) - 3600, ledger))
        self.assertFalse(play.clock_trusted(False, ts(FRI_4PM) + 5, ledger))


class LimitsConfigTest(unittest.TestCase):
    def test_player_without_limits_rejected(self):
        with self.assertRaisesRegex(ProfileError, 'limits'):
            parse_profiles({'profiles': [
                {'id': 'm', 'name': 'M', 'role': 'owner', 'combo': ['1']},
                {'id': 'g', 'name': 'G', 'role': 'guest', 'combo': ['2']}]})

    def test_owner_with_limits_rejected(self):
        with self.assertRaisesRegex(ProfileError, 'owner has no limits'):
            parse_profiles({'profiles': [
                {'id': 'm', 'name': 'M', 'role': 'owner', 'combo': ['1'],
                 'limits': {'hours': {}, 'time': {'minutes': 60, 'per': 'day'}}}]})

    def test_bad_hours_and_periods_rejected(self):
        for limits, msg in [
            ({'hours': {'weekdays': '20:00-15:00'}, 'time': {'minutes': 60, 'per': 'day'}}, 'end before'),
            ({'hours': {'someday': '15:00-20:00'}, 'time': {'minutes': 60, 'per': 'day'}}, 'unknown hours'),
            ({'hours': {}, 'time': {'minutes': 60, 'per': 'fortnight'}}, 'per'),
            ({'hours': {}, 'time': {'minutes': 60, 'per': '3 days'}}, 'from'),
            ({'hours': {}, 'time': {'minutes': -1, 'per': 'day'}}, 'minutes'),
        ]:
            with self.assertRaisesRegex(ProfileError, msg):
                with_limits('theo', limits)

    def test_a_day_overrides_its_group(self):
        profiles = with_limits('theo', {'hours': {'weekdays': '15:00-20:00', 'wed': ['13:00-14:00', '16:00-18:00']},
                                        'time': {'minutes': 60, 'per': 'day'}})
        hours = next(p for p in profiles if p.id == 'theo').limits.hours
        self.assertEqual(hours[2], [(13 * 60, 14 * 60), (16 * 60, 18 * 60)])
        self.assertEqual(hours[5], [])


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_play_is_counted_on_the_monotonic_clock_and_capped_at_its_limit(self):
        ledger = Ledger(self.dir, wall_time=1000)
        ledger.start('theo', 2000, mono=50.0, limit=600.0, boot='b1')
        self.assertFalse(ledger.heartbeat(350.0))
        self.assertEqual(Ledger(self.dir).plays()[-1]['seconds'], 300.0)
        self.assertTrue(ledger.heartbeat(700.0))
        ledger.finish(900.0)
        self.assertEqual(Ledger(self.dir).plays(), [{'profile': 'theo', 'start': 2000, 'seconds': 600.0}])

    def test_a_play_left_open_by_a_power_cut_keeps_its_time(self):
        ledger = Ledger(self.dir, wall_time=1000)
        ledger.start('john', 2000, mono=0.0, limit=None, boot='b1')
        ledger.heartbeat(120.0)
        after_reboot = Ledger(self.dir)
        after_reboot.recover('b2')
        self.assertIsNone(after_reboot.open)
        self.assertEqual(after_reboot.plays(), [{'profile': 'john', 'start': 2000, 'seconds': 120.0}])


if __name__ == '__main__':
    unittest.main()
