"""Combo sign-in at the cabinet (arcade-profiles M-1, AC-1).

Runs anywhere with Python 3.7+ (no evdev needed):
    python3 -m unittest discover -s tests -p 'test_*.py'
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arcade_profiles.profiles import ProfileError, load_profiles, parse_profiles  # noqa: E402
from arcade_profiles.signin import SignIn  # noqa: E402
from arcade_profiles.signin_console import render  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), '..')
PROFILES_PATH = os.path.join(REPO, 'config', 'profiles.json')


def tap(signin, *inputs, now=0.0):
    for name in inputs:
        signin.feed(name, True, now)
        signin.feed(name, False, now)


class ProfilesConfigTest(unittest.TestCase):
    def test_shipped_profiles_are_owner_theo_john_and_guest(self):
        profiles = load_profiles(PROFILES_PATH)
        self.assertEqual([p.name for p in profiles], ['Matt', 'Theo', 'John', 'Guest'])
        self.assertEqual([p.role for p in profiles], ['owner', 'player', 'player', 'guest'])

    def _parse(self, combos):
        roles = ['owner', 'guest'] + ['player'] * (len(combos) - 2)
        return parse_profiles({'profiles': [
            {'id': 'p%d' % i, 'name': 'P%d' % i, 'role': roles[i], 'combo': c}
            for i, c in enumerate(combos)
        ]})

    def test_coin_is_never_part_of_a_combo(self):
        # Coin + anything is a RetroArch hotkey and Coin + Start exits a game (F-2).
        with self.assertRaisesRegex(ProfileError, 'coin'):
            self._parse([['coin', 'start'], ['1']])

    def test_unknown_input_rejected(self):
        with self.assertRaisesRegex(ProfileError, 'unknown input'):
            self._parse([['up', 'select'], ['1']])

    def test_combo_may_not_start_another_combo(self):
        with self.assertRaisesRegex(ProfileError, 'starts with'):
            self._parse([['up', 'up'], ['up', 'up', '1']])

    def test_duplicate_combo_rejected(self):
        with self.assertRaisesRegex(ProfileError, 'starts with'):
            self._parse([['up', '1'], ['up', '1']])

    def test_exactly_one_owner_and_one_guest(self):
        with self.assertRaisesRegex(ProfileError, 'owner'):
            parse_profiles({'profiles': [
                {'id': 'a', 'name': 'A', 'role': 'player', 'combo': ['1']},
                {'id': 'g', 'name': 'G', 'role': 'guest', 'combo': ['2']},
            ]})


class SignInTest(unittest.TestCase):
    def setUp(self):
        self.profiles = load_profiles(PROFILES_PATH)
        self.by_id = {p.id: p for p in self.profiles}
        self.s = SignIn(self.profiles, now=0.0)

    def combo(self, pid):
        return self.by_id[pid].combo

    def test_starts_on_sign_in_screen_with_no_one_signed_in(self):
        self.assertIsNone(self.s.signed_in)
        self.assertEqual(self.s.screen()['view'], 'signin')

    def test_ac1_theo_enters_his_combo_and_is_signed_in(self):
        tap(self.s, *self.combo('theo'))
        self.assertEqual(self.s.signed_in.name, 'Theo')
        screen = self.s.screen()
        self.assertEqual(screen['view'], 'welcome')
        self.assertIn('Theo', screen['title'])

    def test_every_profile_signs_in_with_its_own_combo(self):
        for p in self.profiles:
            s = SignIn(self.profiles, now=0.0)
            tap(s, *p.combo)
            self.assertEqual(s.signed_in, p)

    def test_screen_never_shows_a_combo(self):
        screen = self.s.screen()
        text = ' '.join([screen['title']] + screen['lines'])
        self.assertNotIn('left, right', text.lower())

    def test_progress_counts_inputs_entered(self):
        tap(self.s, *self.combo('theo')[:2])
        self.assertEqual(self.s.screen()['entered'], 2)

    def test_wrong_combo_says_so_and_starts_over(self):
        tap(self.s, 'down', '6')
        screen = self.s.screen()
        self.assertEqual(screen['entered'], 0)
        self.assertIn('not recognised', screen['message'].lower())
        tap(self.s, *self.combo('theo'))
        self.assertEqual(self.s.signed_in.name, 'Theo')

    def test_coin_clears_a_half_entered_combo(self):
        tap(self.s, *self.combo('theo')[:3])
        tap(self.s, 'coin')
        self.assertEqual(self.s.screen()['entered'], 0)
        tap(self.s, *self.combo('john'))
        self.assertEqual(self.s.signed_in.name, 'John')

    def test_idle_entry_times_out(self):
        theo = self.combo('theo')
        tap(self.s, *theo[:3], now=1.0)
        self.s.tick(1.0 + SignIn.ENTRY_TIMEOUT + 0.1)
        self.assertEqual(self.s.screen()['entered'], 0)
        tap(self.s, *theo[3:], now=10.0)
        self.assertIsNone(self.s.signed_in)

    def test_coin_plus_start_is_not_a_guest_sign_in(self):
        # Holding the exit chord must never sign anyone in (F-2).
        self.s.feed('coin', True, 0)
        self.s.feed('start', True, 0)
        self.s.feed('start', False, 0)
        self.s.feed('coin', False, 0)
        self.assertIsNone(self.s.signed_in)

    def test_start_then_coin_held_together_is_not_a_guest_sign_in(self):
        self.s.feed('start', True, 0)
        self.s.feed('coin', True, 0)
        self.s.feed('coin', False, 0)
        self.s.feed('start', False, 0)
        self.assertIsNone(self.s.signed_in)

    def test_coin_in_a_chord_does_not_clear_the_entry(self):
        tap(self.s, *self.combo('theo')[:2])
        self.s.feed('coin', True, 0)
        self.s.feed('start', True, 0)
        self.s.feed('start', False, 0)
        self.s.feed('coin', False, 0)
        self.assertEqual(self.s.screen()['entered'], 2)

    def test_input_held_from_before_the_screen_is_ignored(self):
        # e.g. Start still held from quitting EmulationStation.
        self.s.feed('start', False, 0)
        self.assertIsNone(self.s.signed_in)
        self.assertEqual(self.s.screen()['entered'], 0)

    def test_guest_signs_in_with_start(self):
        tap(self.s, 'start')
        self.assertEqual(self.s.signed_in.role, 'guest')

    def test_welcome_waits_for_a_button_then_is_done(self):
        tap(self.s, *self.combo('theo'))
        self.assertFalse(self.s.done)
        self.s.tick(60.0)
        self.assertFalse(self.s.done)
        tap(self.s, '1')
        self.assertTrue(self.s.done)
        self.assertEqual(self.s.signed_in.name, 'Theo')

    def test_input_after_sign_in_does_not_switch_profile(self):
        tap(self.s, *self.combo('theo'))
        tap(self.s, *self.combo('matt'))
        self.assertEqual(self.s.signed_in.name, 'Theo')


class ConsoleRenderTest(unittest.TestCase):
    def test_sign_in_screen_shows_progress_but_not_the_combo(self):
        profiles = load_profiles(PROFILES_PATH)
        s = SignIn(profiles, now=0.0)
        tap(s, 'left', 'right')
        text = '\n'.join(render(s.screen(), 80, 24))
        self.assertIn('Who is playing?', text)
        self.assertIn('* *', text)
        self.assertNotIn('left', text)

    def test_welcome_names_the_profile(self):
        profiles = load_profiles(PROFILES_PATH)
        s = SignIn(profiles, now=0.0)
        tap(s, *profiles[1].combo)
        text = '\n'.join(render(s.screen(), 80, 24))
        self.assertIn('Signed in: Theo', text)
        self.assertIn('Press any button to play', text)


if __name__ == '__main__':
    unittest.main()
