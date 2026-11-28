"""Whole-cabinet flow in the simulator: sign-in, EmulationStation, a game, and
the flag off path (arcade-profiles M-1); hours and time limits at game start
and during play (M-2)."""

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request

REPO = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, REPO)

from arcade_profiles import settings  # noqa: E402
from arcade_profiles.profiles import load_profiles  # noqa: E402
from sim.cabinet_sim import CabinetSim, SimClock  # noqa: E402
from sim import server  # noqa: E402

PROFILES_JSON = os.path.join(REPO, 'config', 'profiles.json')
PROFILES = load_profiles(PROFILES_JSON)
COMBOS = {p.id: p.combo for p in PROFILES}


def cabinet(state_dir, enforce, clock):
    """A simulated cabinet whose settings hold the shipped profiles and the given flag."""
    with open(PROFILES_JSON) as f:
        settings.write({'enforce': enforce, 'profiles': json.load(f)}, state_dir)
    return CabinetSim(state_dir, clock)


FRI_4PM = dt.datetime(2026, 11, 27, 16, 0)


def frozen_clock(at=FRI_4PM):
    """Time only moves when a test advances it."""
    return SimClock(wall=at.timestamp(), mono_source=lambda: 0.0)


class CabinetSimTest(unittest.TestCase):
    def setUp(self):
        self.state_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state_dir)
        self.clock = frozen_clock()

    def boot(self, enforce):
        return cabinet(self.state_dir, enforce, self.clock)

    def tap(self, sim, *names):
        for n in names:
            sim.feed(n, True)
            sim.feed(n, False)

    def exit_chord(self, sim):
        sim.feed('coin', True)
        sim.feed('start', True)
        sim.feed('start', False)
        sim.feed('coin', False)

    def session(self):
        path = os.path.join(self.state_dir, 'session.json')
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def quit_emulationstation(self, sim):
        self.tap(sim, 'start')           # ES main menu
        self.assertEqual(sim.view, 'esmenu')
        self.tap(sim, '1')               # "Quit EmulationStation" is first

    def test_flag_on_boots_to_sign_in(self):
        sim = self.boot(True)
        self.assertEqual(sim.view, 'signin')
        self.assertIsNone(self.session())

    def test_ac1_theo_signs_in_and_cabinet_shows_him(self):
        sim = self.boot(True)
        self.tap(sim, *COMBOS['theo'])
        self.assertEqual(sim.view, 'welcome')
        self.assertIn('Theo', sim.state()['screen']['title'])
        self.assertEqual(self.session()['profile'], 'theo')
        self.tap(sim, '1')
        self.assertEqual(sim.view, 'menu')
        self.assertEqual(sim.state()['session']['name'], 'Theo')

    def test_combo_never_fires_inside_a_game(self):
        sim = self.boot(True)
        self.tap(sim, *COMBOS['theo'])
        self.tap(sim, '1')
        self.tap(sim, '1')               # launch the highlighted game
        self.assertEqual(sim.view, 'game')
        self.tap(sim, *COMBOS['matt'])
        self.tap(sim, *COMBOS['guest'])
        self.assertEqual(sim.view, 'game')
        self.assertEqual(self.session()['profile'], 'theo')

    def test_coin_start_still_exits_a_game_when_signed_in(self):
        sim = self.boot(True)
        self.tap(sim, *COMBOS['john'])
        self.tap(sim, '1')
        self.tap(sim, '1')
        self.exit_chord(sim)
        self.assertEqual(sim.view, 'menu')
        self.assertEqual(self.session()['profile'], 'john')

    def test_quitting_emulationstation_returns_to_sign_in_for_the_next_player(self):
        sim = self.boot(True)
        self.tap(sim, *COMBOS['theo'])
        self.tap(sim, '1')
        self.quit_emulationstation(sim)
        self.assertEqual(sim.view, 'signin')
        self.assertIsNone(self.session())
        self.tap(sim, *COMBOS['guest'])
        self.assertEqual(self.session()['profile'], 'guest')

    def test_flag_off_boots_and_plays_as_before(self):
        sim = self.boot(False)
        self.assertEqual(sim.view, 'menu')
        self.tap(sim, '1')
        self.assertEqual(sim.view, 'game')
        self.tap(sim, *COMBOS['theo'])
        self.assertEqual(sim.view, 'game')
        self.exit_chord(sim)
        self.assertEqual(sim.view, 'menu')
        self.quit_emulationstation(sim)
        self.assertEqual(sim.view, 'shell')   # as before: ES quits to the console
        self.assertIsNone(self.session())
        self.assertIsNone(sim.state()['session'])


class LimitsInSimTest(unittest.TestCase):
    """M-2 scenarios walked through the simulated cabinet, flag on."""

    def setUp(self):
        self.state_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state_dir)
        self.clock = frozen_clock()
        self.sim = cabinet(self.state_dir, True, self.clock)

    def tap(self, *names):
        for n in names:
            self.sim.feed(n, True)
            self.sim.feed(n, False)

    def dismiss(self):
        self.sim.tick()
        if self.sim.view in ('refused', 'timeup'):
            self.clock.advance(2)
            self.tap('1')
            self.assertEqual(self.sim.view, 'menu')

    def sign_in(self, pid):
        self.dismiss()
        if self.sim.view != 'signin':
            self.tap('start')
            self.tap('1')                # ES menu: Quit EmulationStation
        self.assertEqual(self.sim.view, 'signin')
        self.tap(*COMBOS[pid])
        self.assertEqual(self.sim.view, 'welcome')
        welcome = self.sim.state()['screen']
        self.tap('1')
        self.assertEqual(self.sim.view, 'menu')
        return welcome

    def start_game(self):
        self.dismiss()
        self.tap('1')
        return self.sim.state()

    def exit_game(self):
        self.sim.feed('coin', True)
        self.sim.feed('start', True)
        self.sim.feed('start', False)
        self.sim.feed('coin', False)

    def play_minutes(self, minutes):
        state = self.start_game()
        self.assertEqual(state['view'], 'game', state.get('screen'))
        self.clock.advance(minutes * 60)
        state = self.sim.state()
        if state['view'] == 'game':
            self.exit_game()
            state = self.sim.state()
        return state

    def text(self, state):
        return '\n'.join([state['screen']['title']] + state['screen']['lines'])

    def test_welcome_says_time_left(self):
        welcome = self.sign_in('theo')
        self.assertIn('Time left: 1 h 00 min (play until 5:00 pm)', welcome['lines'])
        self.assertEqual(self.sign_in('matt')['lines'][1], 'No time limit')

    def test_ac2_outside_hours_game_does_not_start_and_says_when(self):
        self.clock.set_wall(dt.datetime(2026, 11, 27, 10, 0).timestamp())
        welcome = self.sign_in('theo')
        self.assertIn('Not play time:', welcome['lines'])
        state = self.start_game()
        self.assertEqual(state['view'], 'refused')
        self.assertIsNone(self.sim.game)
        self.assertIn('Not play time', self.text(state))
        self.assertIn('Next play: today at 3:00 pm', self.text(state))
        self.assertIn('The game did not start.', self.text(state))

    def test_refusal_clears_on_a_button_or_by_itself(self):
        self.clock.set_wall(dt.datetime(2026, 11, 27, 10, 0).timestamp())
        self.sign_in('theo')
        self.start_game()
        self.tap('1')                    # too soon: the screen stays
        self.assertEqual(self.sim.view, 'refused')
        self.clock.advance(2)
        self.tap('1')
        self.assertEqual(self.sim.view, 'menu')
        self.start_game()
        self.clock.advance(11)
        self.assertEqual(self.sim.state()['view'], 'menu')

    def test_ac3_used_up_game_does_not_start_and_says_so(self):
        self.sign_in('theo')
        self.play_minutes(60)
        state = self.start_game()
        self.assertEqual(state['view'], 'refused')
        self.assertIn('Time is used up', self.text(state))
        self.assertIn("Theo's 60 min for today are used up", self.text(state))

    def test_ac4_game_is_stopped_at_the_limit(self):
        self.sign_in('theo')
        state = self.start_game()
        self.clock.advance(59 * 60)
        self.assertEqual(self.sim.state()['view'], 'game')
        self.clock.advance(2 * 60)
        state = self.sim.state()
        self.assertEqual(state['view'], 'timeup')
        self.assertIsNone(self.sim.game)
        self.assertIn('Time is up', self.text(state))
        theo = next(u for u in state['usage'] if u['id'] == 'theo')
        self.assertEqual(theo['used'], 3600)        # counted to the limit, not past it
        self.assertEqual(theo['left'], 0)

    def test_ac4_owner_theo_john_guest_past_the_kids_limits(self):
        self.clock.set_wall(dt.datetime(2026, 11, 28, 9, 0).timestamp())   # Saturday
        for pid, limit in (('theo', 60), ('john', 60)):
            self.sign_in(pid)
            self.assertEqual(self.play_minutes(90)['view'], 'timeup')
            self.assertEqual(self.start_game()['view'], 'refused')
        self.sign_in('matt')
        self.assertEqual(self.play_minutes(180)['view'], 'menu')    # played and exited, no stop
        self.assertEqual(self.start_game()['view'], 'game')
        self.exit_game()

    def test_ac4_guest_stops_at_its_own_half_hour(self):
        self.sign_in('guest')
        state = self.play_minutes(45)
        self.assertEqual(state['view'], 'timeup')
        guest = next(u for u in state['usage'] if u['id'] == 'guest')
        self.assertEqual(guest['used'], 30 * 60)

    def test_ac7_mh2_theo_out_of_time_cannot_play_as_guest(self):
        self.sign_in('theo')
        self.play_minutes(60)
        welcome = self.sign_in('guest')
        self.assertIn('Guest play is paused:', welcome['lines'])
        state = self.start_game()
        self.assertEqual(state['view'], 'refused')
        self.assertIn('Guest play is paused', self.text(state))
        self.clock.advance(3600)
        self.assertEqual(self.start_game()['view'], 'refused')

    def test_time_is_counted_across_games_and_sign_ins(self):
        self.sign_in('john')
        self.play_minutes(20)
        self.sign_in('john')
        self.play_minutes(25)
        self.sign_in('john')
        state = self.play_minutes(30)
        self.assertEqual(state['view'], 'timeup')
        john = next(u for u in state['usage'] if u['id'] == 'john')
        self.assertEqual(john['used'], 3600)

    def test_power_cycle_mid_game_keeps_the_time_played(self):
        self.sign_in('theo')
        self.start_game()
        self.clock.advance(40 * 60)
        self.sim.state()                  # a heartbeat
        sim = cabinet(self.state_dir, True, self.clock)
        theo = next(u for u in sim.state()['usage'] if u['id'] == 'theo')
        self.assertEqual(theo['used'], 40 * 60)

    def test_dec1_unsynced_clock_only_the_owner_plays(self):
        self.clock.synced = False
        self.sign_in('theo')
        state = self.start_game()
        self.assertEqual(state['view'], 'refused')
        self.assertIn('only Matt can play', self.text(state))
        self.sign_in('guest')
        self.assertEqual(self.start_game()['view'], 'refused')
        self.sign_in('matt')
        self.assertEqual(self.start_game()['view'], 'game')

    def test_nothing_at_the_cabinet_changes_a_limit(self):
        # MH-1: every panel input, on every screen, leaves the rules as they were.
        before = repr([p.limits for p in PROFILES])
        self.sign_in('matt')
        for name in ('up', 'down', 'left', 'right', '1', '2', '3', '4', '5', '6', 'coin', 'start'):
            self.tap(name)
        self.assertEqual(repr([p.limits for p in self.sim.profiles]), before)


class FlagOffLimitsTest(unittest.TestCase):
    def test_flag_off_plays_at_any_hour_for_any_time_with_nothing_counted(self):
        state_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state_dir)
        clock = frozen_clock(dt.datetime(2026, 11, 27, 2, 0))
        clock.synced = False
        sim = cabinet(state_dir, False, clock)
        sim.feed('1', True)
        sim.feed('1', False)
        self.assertEqual(sim.view, 'game')
        clock.advance(5 * 3600)
        state = sim.state()
        self.assertEqual(state['view'], 'game')
        self.assertIsNone(state['usage'])
        self.assertFalse({'usage.json', 'session.json'} & set(os.listdir(state_dir)))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.state_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state_dir)
        cabinet = os.path.join(REPO, 'config', 'cabinet.dev.json')
        self.httpd = server.make_server(0, cabinet, os.path.join(REPO, 'config', 'profiles.json'),
                                        self.state_dir)
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    def test_page_is_served(self):
        with urllib.request.urlopen(self.base + '/') as resp:
            self.assertIn(b'Pi Arcade', resp.read())

    def test_sign_in_over_http(self):
        self.assertEqual(self.call('/api/state')['view'], 'signin')
        for n in COMBOS['theo']:
            self.call('/api/input', {'input': n, 'pressed': True})
            state = self.call('/api/input', {'input': n, 'pressed': False})
        self.assertEqual(state['view'], 'welcome')
        self.assertEqual(state['session']['name'], 'Theo')
        self.assertTrue(state['enforce'])

    def test_clock_can_be_set_and_advanced(self):
        state = self.call('/api/clock', {'set': '2026-11-27T10:00'})
        self.assertEqual(state['clock']['wall'], '2026-11-27T10:00')
        state = self.call('/api/clock', {'advance': 3600, 'synced': False})
        self.assertEqual(state['clock']['wall'], '2026-11-27T11:00')
        self.assertFalse(state['clock']['synced'])

    def test_reset_usage_forgets_every_play(self):
        state = self.call('/api/clock', {'set': '2026-11-27T16:00'})
        for n in COMBOS['theo'] + ('1', '1'):
            self.call('/api/input', {'input': n, 'pressed': True})
            state = self.call('/api/input', {'input': n, 'pressed': False})
        self.assertEqual(state['view'], 'game')
        state = self.call('/api/reset-usage', {})
        self.assertEqual(state['view'], 'signin')
        self.assertEqual([u['used'] for u in state['usage']], [0, 0, 0, 0])

    def test_reboot_rereads_the_flag(self):
        state = self.call('/api/boot', {})
        self.assertEqual(state['view'], 'signin')


if __name__ == '__main__':
    unittest.main()
