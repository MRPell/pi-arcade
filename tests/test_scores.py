"""Arcade profiles M-4: an idle cabinet rotates through every game's high score
and names the profile that holds each (AC-5); the owner changes who holds a
score from their computer and the rotating screen follows (AC-6); nothing at
the cabinet can change it (MH-1); with the flag off nothing changes (MH-4).

Walked in the simulator, which runs the real high-score code against the
hiscore saves its stand-in games write, and through the runcommand hooks the
Pi runs."""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, REPO)

from admin import server as admin  # noqa: E402
from arcade_profiles import scores, settings  # noqa: E402
from arcade_profiles.profiles import load_profiles  # noqa: E402
from sim import cabinet_sim  # noqa: E402
from sim.cabinet_sim import CabinetSim, SimClock  # noqa: E402
from sim.server import fresh_cabinet  # noqa: E402

PROFILES_JSON = os.path.join(REPO, 'config', 'profiles.json')
DEV_CABINET = os.path.join(REPO, 'config', 'cabinet.dev.json')
OFF_CABINET = os.path.join(REPO, 'config', 'cabinet.json')
PROFILES = load_profiles(PROFILES_JSON)
GAMES = scores.load_games()
SAT_10AM = dt.datetime(2026, 11, 28, 10, 0)
INPUTS = ('up', 'down', 'left', 'right', '1', '2', '3', '4', '5', '6', 'coin', 'start')
TITLES = [title for title, _ in cabinet_sim.GAMES]


class HiscoreFileTest(unittest.TestCase):
    def test_shipped_games_read_their_top_score(self):
        self.assertEqual(set(GAMES), {'pacman', 'galaga', 'dkong', 'invaders'})
        for game in GAMES.values():
            for score in (0, 7650, 123450):
                if score >= 10 ** (game.length * (2 if game.encoding == 'bcd-le' else 1)):
                    continue
                self.assertEqual(scores.decode(game, scores.encode(game, score)), score, game.rom)

    def test_factory_saves(self):
        # Donkey Kong ships with 7,650 at the top, saved as BCD 50 76 00.
        dkong = GAMES['dkong']
        self.assertEqual(scores.decode(dkong, b'\0' * 170 + bytes([0x50, 0x76, 0x00])), 7650)
        # Galaga's top score as screen digits, lowest first, blank 0x24: 20000.
        galaga = GAMES['galaga']
        self.assertEqual(scores.decode(galaga, b'\0' * 45 + bytes([0, 0, 0, 0, 2, 0x24])), 20000)

    def test_unreadable_saves_are_skipped(self):
        pacman = GAMES['pacman']
        self.assertIsNone(scores.decode(pacman, b'\x01'))              # too short
        self.assertIsNone(scores.decode(pacman, bytes([0xAB, 0, 0, 0])))  # not BCD

    def test_encode_keeps_the_rest_of_the_save(self):
        dkong = GAMES['dkong']
        data = bytes(range(200))
        out = scores.encode(dkong, 12300, data)
        self.assertEqual(len(out), 200)
        self.assertEqual(out[:170], data[:170])
        self.assertEqual(out[173:], data[173:])


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.hi = os.path.join(self.dir, 'hi')
        os.makedirs(self.hi)

    def save(self, rom, score):
        game = GAMES[rom]
        with open(os.path.join(self.hi, game.file), 'wb') as f:
            f.write(scores.encode(game, score))

    def sync(self, holder):
        return scores.sync(self.dir, holder, 0, GAMES, self.hi)

    def test_a_new_top_score_goes_to_who_played_and_an_unchanged_one_stays(self):
        self.save('pacman', 1000)
        self.assertEqual(self.sync(None), ['pacman'])      # before a game: set before profiles
        self.save('pacman', 2500)
        self.save('galaga', 3000)
        self.assertEqual(sorted(self.sync('theo')), ['galaga', 'pacman'])
        self.assertEqual(self.sync('john'), [])
        board = {r['game']: r for r in scores.rows(self.dir, PROFILES, GAMES)}
        self.assertEqual((board['pacman']['score'], board['pacman']['holder_name']), (2500, 'Theo'))
        self.assertEqual(board['galaga']['holder'], 'theo')

    def test_owner_reassigns_all_or_nothing(self):
        self.save('pacman', 1000)
        self.save('galaga', 2000)
        self.sync('theo')
        with self.assertRaises(scores.ScoreError):
            scores.assign(self.dir, {'pacman': 'john', 'galaga': 'nobody'}, PROFILES)
        with self.assertRaises(scores.ScoreError):
            scores.assign(self.dir, {'frogger': 'john'}, PROFILES)
        self.assertEqual({r['holder'] for r in scores.rows(self.dir, PROFILES, GAMES)}, {'theo'})
        scores.assign(self.dir, {'pacman': 'john', 'galaga': None}, PROFILES)
        board = {r['game']: r['holder'] for r in scores.rows(self.dir, PROFILES, GAMES)}
        self.assertEqual(board, {'pacman': 'john', 'galaga': None})

    def test_a_removed_profiles_score_shows_no_profile(self):
        self.save('pacman', 1000)
        self.sync('theo')
        rest = [p for p in PROFILES if p.id != 'theo']
        self.assertIsNone(scores.rows(self.dir, rest, GAMES)[0]['holder_name'])


class AttractTest(unittest.TestCase):
    ROWS = [{'game': 'galaga', 'title': 'Galaga', 'score': 3000, 'holder': 'john', 'holder_name': 'John'},
            {'game': 'pacman', 'title': 'Pac-Man', 'score': 1200, 'holder': None, 'holder_name': None}]

    def test_idle_then_rotates_then_any_input_wakes(self):
        a = scores.Attract(0.0)
        self.assertFalse(a.tick(29.9, True))
        self.assertTrue(a.tick(30.0, True))
        self.assertEqual(a.screen(30.0, self.ROWS)['lines'][:3], ['Galaga', '3,000', 'Held by John'])
        self.assertEqual(a.screen(35.0, self.ROWS)['lines'][:3], ['Pac-Man', '1,200', 'Held by no profile'])
        self.assertEqual(a.screen(40.0, self.ROWS)['lines'][0], 'Galaga')
        self.assertTrue(a.input(41.0))
        self.assertFalse(a.active)
        self.assertFalse(a.input(42.0))      # sign-in is up: inputs go to it
        self.assertFalse(a.tick(71.0, True))
        self.assertTrue(a.tick(72.0, True))

    def test_never_without_scores_or_while_a_combo_is_being_entered(self):
        a = scores.Attract(0.0)
        self.assertFalse(a.tick(100.0, False))


class SimScoresTest(unittest.TestCase):
    cabinet_config = DEV_CABINET

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        fresh_cabinet(self.dir, self.cabinet_config, PROFILES_JSON)
        self.mono = 0.0
        self.clock = SimClock(wall=SAT_10AM.timestamp(), mono_source=lambda: self.mono)
        self.sim = CabinetSim(self.dir, self.clock)

    def wait(self, seconds):
        self.mono += seconds

    def tap(self, *names):
        for n in names:
            self.sim.feed(n, True)
            self.sim.feed(n, False)

    def combo(self, pid):
        return next(p.combo for p in self.sim.profiles if p.id == pid)

    def sign_in(self, pid):
        self.assertEqual(self.sim.view, 'signin')
        self.tap(*self.combo(pid))
        self.assertEqual(self.sim.view, 'welcome')
        self.tap('1')
        self.assertEqual(self.sim.view, 'menu')

    def play(self, title, *presses):
        while TITLES[self.sim.cursor] != title:
            self.tap('down')
        self.tap('1')
        self.assertEqual(self.sim.view, 'game', self.sim.state().get('screen'))
        self.tap(*presses)
        self.sim.feed('coin', True)
        self.sim.feed('start', True)
        self.sim.feed('start', False)
        self.sim.feed('coin', False)
        self.assertEqual(self.sim.view, 'menu')

    def quit_es(self):
        self.tap('start', '1')

    def cards(self, n):
        out = []
        for _ in range(n):
            state = self.sim.state()
            self.assertEqual(state['view'], 'scores', state.get('screen'))
            out.append(tuple(state['screen']['lines'][:3]))
            self.wait(scores.Attract.CARD_SECONDS)
        return out

    def setup_scores(self):
        """Theo sets Pac-Man, John sets Galaga, the owner sets Donkey Kong."""
        self.sign_in('theo')
        self.play('Pac-Man', '1', '1', '2')           # 1,200
        self.quit_es()
        self.sign_in('john')
        self.play('Galaga', '2', '2', '2')            # 3,000
        self.quit_es()
        self.sign_in('matt')
        self.play('Donkey Kong', *['2'] * 9)          # 9,000
        self.quit_es()

    def test_ac5_idle_cabinet_rotates_every_high_score_and_names_its_holder(self):
        self.setup_scores()
        self.assertEqual(self.sim.view, 'signin')
        self.wait(29)
        self.assertEqual(self.sim.state()['view'], 'signin')
        self.wait(1)
        self.assertEqual(sorted(self.cards(3)), [('Donkey Kong', '9,000', 'Held by Matt'),
                                                 ('Galaga', '3,000', 'Held by John'),
                                                 ('Pac-Man', '1,200', 'Held by Theo')])
        self.assertEqual(self.cards(1)[0][0], 'Donkey Kong')   # round again

    def test_ac5_a_press_brings_sign_in_back_and_is_not_part_of_a_combo(self):
        self.setup_scores()
        self.wait(30)
        self.assertEqual(self.sim.state()['view'], 'scores')
        combo = self.combo('theo')
        self.tap(combo[0])                       # wakes the screen only
        state = self.sim.state()
        self.assertEqual(state['view'], 'signin')
        self.assertEqual(state['screen']['entered'], 0)
        self.tap(*combo)
        self.assertEqual(self.sim.view, 'welcome')

    def test_a_beaten_score_moves_to_the_new_holder_and_a_lower_one_does_not(self):
        self.setup_scores()
        self.sign_in('john')
        self.play('Pac-Man', '2', '2')           # 2,000 beats Theo's 1,200
        self.play('Galaga', '1')                 # 100 does not beat his own 3,000
        board = {r['title']: (r['score'], r['holder_name']) for r in self.sim.state()['scores']}
        self.assertEqual(board['Pac-Man'], (2000, 'John'))
        self.assertEqual(board['Galaga'], (3000, 'John'))

    def test_no_scores_yet_sign_in_stays_up(self):
        self.wait(120)
        self.assertEqual(self.sim.state()['view'], 'signin')

    def test_a_half_entered_combo_is_not_interrupted(self):
        self.setup_scores()
        self.tap(self.combo('theo')[0])
        self.wait(4)
        self.assertEqual(self.sim.state()['view'], 'signin')
        self.wait(26)        # the entry cleared after 5 s; 30 s since the last input
        self.assertEqual(self.sim.state()['view'], 'scores')


class FlagOffScoresTest(SimScoresTest):
    cabinet_config = OFF_CABINET

    def test_mh4_flag_off_no_sign_in_no_high_score_screen_and_nothing_credited(self):
        self.assertEqual(self.sim.view, 'menu')
        self.play('Pac-Man', '2')
        self.wait(600)
        self.assertEqual(self.sim.state()['view'], 'menu')
        self.assertFalse(os.path.exists(os.path.join(self.dir, scores.FILE)))

    def test_a_score_set_with_the_flag_off_holds_no_profile_once_on(self):
        self.play('Pac-Man', '2')
        settings.write({'enforce': True}, self.dir)
        self.quit_es()
        self.sign_in('theo')
        self.play('Galaga', '1')
        board = {r['title']: r['holder_name'] for r in self.sim.state()['scores']}
        self.assertEqual(board, {'Pac-Man': None, 'Galaga': 'Theo'})

    test_ac5_idle_cabinet_rotates_every_high_score_and_names_its_holder = None
    test_ac5_a_press_brings_sign_in_back_and_is_not_part_of_a_combo = None
    test_a_beaten_score_moves_to_the_new_holder_and_a_lower_one_does_not = None
    test_no_scores_yet_sign_in_stays_up = None
    test_a_half_entered_combo_is_not_interrupted = None


class AdminScoresTest(SimScoresTest):
    def setUp(self):
        super().setUp()
        self.httpd = admin.make_server(0, admin.sim_cabinet(self.dir))
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read().decode())

    def board_file(self):
        with open(os.path.join(self.dir, scores.FILE), 'rb') as f:
            return f.read()

    def test_ac6_owner_changes_who_holds_a_score_and_the_rotating_screen_follows(self):
        self.setup_scores()
        status, state = self.call('/api/cabinet')
        self.assertEqual(status, 200, state)
        self.assertIn({'game': 'pacman', 'title': 'Pac-Man', 'score': 1200,
                       'holder': 'theo', 'holder_name': 'Theo'}, state['scores'])
        self.wait(30)
        self.assertIn(('Pac-Man', '1,200', 'Held by Theo'), self.cards(3))
        # The rotation is up while the owner makes the change.
        status, state = self.call('/api/scores', {'game': 'pacman', 'holder': 'john'})
        self.assertEqual(status, 200, state)
        self.assertIn(('Pac-Man', '1,200', 'Held by John'), self.cards(3))

    def test_ac6_a_score_with_no_profile_is_given_one(self):
        self.play_with_flag_off_first()
        status, state = self.call('/api/scores', {'game': 'pacman', 'holder': 'theo'})
        self.assertEqual(status, 200, state)
        self.wait(30)
        self.assertIn(('Pac-Man', '2,000', 'Held by Theo'), self.cards(2))
        status, state = self.call('/api/scores', {'game': 'pacman', 'holder': None})
        self.assertEqual(status, 200, state)
        self.assertIn(('Pac-Man', '2,000', 'Held by no profile'), self.cards(2))

    def play_with_flag_off_first(self):
        hi = os.path.join(self.dir, 'hi')
        os.makedirs(hi, exist_ok=True)
        with open(os.path.join(hi, GAMES['pacman'].file), 'wb') as f:
            f.write(scores.encode(GAMES['pacman'], 2000))   # set before profiles
        self.sign_in('theo')
        self.play('Galaga', '1')                            # the game-start check notes it
        self.quit_es()
        board = {r['game']: r['holder'] for r in self.call('/api/cabinet')[1]['scores']}
        self.assertIsNone(board['pacman'])

    def test_bad_score_changes_are_refused_and_change_nothing(self):
        self.setup_scores()
        before = self.board_file()
        for body in ({'game': 'pacman', 'holder': 'nobody'}, {'game': 'frogger', 'holder': 'theo'},
                     {'game': 'pacman'} | {'holder': 3}, {'holder': 'theo'}):
            status, answer = self.call('/api/scores', body)
            self.assertIn(status, (400, 502), body)
            self.assertIn('error', answer)
        self.assertEqual(self.board_file(), before)

    def test_mh1_no_control_at_the_cabinet_changes_who_holds_a_score(self):
        self.setup_scores()
        before = scores.read_board(self.dir)['games']
        self.wait(30)
        for view in ('scores', 'signin'):
            for n in INPUTS:
                self.tap(n)
                self.sim.feed('coin', True)
                self.tap(n)
                self.sim.feed('coin', False)
            self.wait(30)
        # Every input on every screen, games included (a game played may set a
        # new score of its own); none of the scores already there changed hands.
        after = scores.read_board(self.dir)['games']
        self.assertEqual({rom: after[rom] for rom in before}, before)


class HookScoresTest(unittest.TestCase):
    """The runcommand hooks on the Pi read the hiscore saves and credit them."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, 'state')
        self.hi = os.path.join(self.tmp, 'hi')
        os.makedirs(self.hi)
        os.makedirs(self.state)
        self.env = dict(os.environ, PI_ARCADE_DIR=REPO, PI_ARCADE_STATE_DIR=self.state,
                        PI_ARCADE_HISCORE_DIR=self.hi, PYTHONPATH=os.path.join(REPO, 'src'))
        self.env.pop('ARCADE_PROFILES_ENFORCED', None)

    def save(self, rom, score):
        with open(os.path.join(self.hi, GAMES[rom].file), 'wb') as f:
            f.write(scores.encode(GAMES[rom], score))

    def gate(self, *args):
        return subprocess.run([sys.executable, '-m', 'arcade_profiles.gate_console'] + list(args),
                              env=self.env, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_start_and_end_credit_a_new_top_score_to_who_played(self):
        self.save('dkong', 7650)                     # the factory score
        with open(os.path.join(self.state, 'session.json'), 'w') as f:
            json.dump({'profile': 'matt'}, f)
        result = self.gate('start', str(os.getpid()))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.save('dkong', 12300)                    # the game saved a new top score on exit
        result = self.gate('end')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        board = scores.read_board(self.state)['games']
        self.assertEqual((board['dkong']['score'], board['dkong']['holder']), (12300, 'matt'))

    def test_settings_command_reassigns_on_the_cabinet(self):
        self.save('pacman', 500)
        scores.sync(self.state, 'theo', 0, GAMES, self.hi)
        result = subprocess.run([sys.executable, '-m', 'arcade_profiles.settings', 'write'],
                                input=json.dumps({'scores': {'pacman': 'john'}}).encode(),
                                env=self.env, timeout=30, stdout=subprocess.PIPE)
        self.assertEqual(result.returncode, 0)
        shown = json.loads(result.stdout.decode())
        self.assertEqual(shown['scores'][0]['holder_name'], 'John')


if __name__ == '__main__':
    unittest.main()
