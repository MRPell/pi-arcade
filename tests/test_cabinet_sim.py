"""Whole-cabinet flow in the simulator: sign-in, EmulationStation, a game, and
the flag off path (arcade-profiles M-1)."""

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

from arcade_profiles.profiles import load_profiles  # noqa: E402
from sim.cabinet_sim import CabinetSim  # noqa: E402
from sim import server  # noqa: E402

PROFILES = load_profiles(os.path.join(REPO, 'config', 'profiles.json'))
COMBOS = {p.id: p.combo for p in PROFILES}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class CabinetSimTest(unittest.TestCase):
    def setUp(self):
        self.state_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state_dir)
        self.clock = Clock()

    def boot(self, enforce):
        return CabinetSim(PROFILES, enforce=enforce, state_dir=self.state_dir, clock=self.clock)

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

    def test_reboot_rereads_the_flag(self):
        state = self.call('/api/boot', {})
        self.assertEqual(state['view'], 'signin')


if __name__ == '__main__':
    unittest.main()
