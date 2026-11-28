"""Arcade profiles M-3: the owner changes profiles, combos, hours, time limits
and the flag from their computer (admin/), and the cabinet applies them with
no restart; nothing at the cabinet can make those changes (MH-1).

Walked through the admin's HTTP API against the simulated cabinet, which
reads the same settings files the Pi does, and through the SSH path with a
stand-in ssh that runs the remote command locally."""

import copy
import datetime as dt
import json
import os
import shutil
import stat
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
from arcade_profiles import settings  # noqa: E402
from sim.cabinet_sim import CabinetSim, SimClock  # noqa: E402
from sim.server import fresh_cabinet  # noqa: E402

PROFILES_JSON = os.path.join(REPO, 'config', 'profiles.json')
DEV_CABINET = os.path.join(REPO, 'config', 'cabinet.dev.json')
OFF_CABINET = os.path.join(REPO, 'config', 'cabinet.json')
FRI_4PM = dt.datetime(2026, 11, 27, 16, 0)
INPUTS = ('up', 'down', 'left', 'right', '1', '2', '3', '4', '5', '6', 'coin', 'start')


class AdminTest(unittest.TestCase):
    cabinet_config = DEV_CABINET

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        fresh_cabinet(self.dir, self.cabinet_config, PROFILES_JSON)
        self.clock = SimClock(wall=FRI_4PM.timestamp(), mono_source=lambda: 0.0)
        self.sim = CabinetSim(self.dir, self.clock)
        self.httpd = admin.make_server(0, self.cabinet())
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def cabinet(self):
        return admin.sim_cabinet(self.dir)

    # -- the owner's computer -------------------------------------------- #

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

    def owner_edits(self, edit):
        status, state = self.call('/api/cabinet')
        self.assertEqual(status, 200, state)
        profiles = copy.deepcopy(state['profiles'])
        edit({p['id']: p for p in profiles['profiles']})
        return self.call('/api/profiles', {'profiles': profiles})

    def set_minutes(self, pid, minutes):
        def edit(by_id):
            by_id[pid]['limits']['time']['minutes'] = minutes
        status, state = self.owner_edits(edit)
        self.assertEqual(status, 200, state)

    # -- the cabinet ----------------------------------------------------- #

    def tap(self, *names):
        for n in names:
            self.sim.feed(n, True)
            self.sim.feed(n, False)

    def combo(self, pid):
        return next(p.combo for p in self.sim.profiles if p.id == pid)

    def text(self, state=None):
        state = state or self.sim.state()
        screen = state.get('screen') or {}
        return '\n'.join([screen.get('title', '')] + screen.get('lines', []))

    def quit_es(self):
        self.tap('start')
        self.assertEqual(self.sim.view, 'esmenu')
        self.tap('1')

    def sign_in(self, pid):
        if self.sim.view == 'welcome':
            self.tap('1')
        if self.sim.view in ('menu', 'refused', 'timeup'):
            self.sim.view = 'menu'
            self.quit_es()
        self.assertEqual(self.sim.view, 'signin')
        self.tap(*self.combo(pid))
        self.assertEqual(self.sim.view, 'welcome', self.text())
        return self.text()

    def play(self):
        self.tap('1')
        self.assertEqual(self.sim.view, 'menu')
        self.tap('1')
        return self.sim.state()

    def settings_files(self):
        out = {}
        for name in (settings.CABINET, settings.PROFILES):
            with open(os.path.join(self.dir, name), 'rb') as f:
                out[name] = f.read()
        return out


class ProfilesFromComputerTest(AdminTest):
    def test_admin_shows_what_the_cabinet_has(self):
        status, state = self.call('/api/cabinet')
        self.assertEqual(status, 200)
        self.assertTrue(state['enforce'])
        theo = next(p for p in state['profiles']['profiles'] if p['id'] == 'theo')
        self.assertEqual(theo['limits']['time']['minutes'], 60)
        self.assertIn('simulator', state['target'])

    def test_ac8_owner_raises_theo_to_90_minutes_and_the_cabinet_allows_90(self):
        self.assertIn('Time left: 1 h 00 min', self.sign_in('theo'))
        self.set_minutes('theo', 90)
        self.assertIn('Time left: 1 h 30 min', self.sign_in('theo'))   # no restart
        self.assertEqual(self.play()['view'], 'game')
        self.clock.advance(61 * 60)
        self.assertEqual(self.sim.state()['view'], 'game')             # past the old hour
        self.clock.advance(29 * 60)
        state = self.sim.state()
        self.assertEqual(state['view'], 'timeup')
        self.assertIn("Theo's 90 min for today are used up", self.text(state))
        theo = next(u for u in state['usage'] if u['id'] == 'theo')
        self.assertEqual(theo['used'], 90 * 60)

    def test_ac8_mh1_no_control_at_the_cabinet_changes_a_setting(self):
        before = self.settings_files()
        # Every input, alone and with Coin held, on every screen the cabinet shows.
        for pid in ('matt', 'theo', 'guest'):
            self.sign_in(pid)
            for screen in range(4):
                for n in INPUTS:
                    self.tap(n)
                    self.sim.feed('coin', True)
                    self.tap(n)
                    self.sim.feed('coin', False)
            self.sim.view = 'menu'
        self.assertEqual(self.settings_files(), before)

    def test_mh1_admin_listens_only_on_this_computer(self):
        self.assertEqual(self.httpd.server_address[0], '127.0.0.1')

    def test_raising_the_limit_applies_to_a_game_already_running(self):
        self.sign_in('theo')
        self.play()
        self.clock.advance(50 * 60)
        self.sim.state()
        self.set_minutes('theo', 90)
        self.clock.advance(20 * 60)
        self.assertEqual(self.sim.state()['view'], 'game')
        self.clock.advance(20 * 60)
        self.assertEqual(self.sim.state()['view'], 'timeup')

    def test_lowering_the_limit_stops_a_running_game_and_keeps_the_time_played(self):
        self.sign_in('theo')
        self.play()
        self.clock.advance(40 * 60)
        self.sim.state()
        self.set_minutes('theo', 30)
        state = self.sim.state()
        self.assertEqual(state['view'], 'timeup')
        theo = next(u for u in state['usage'] if u['id'] == 'theo')
        self.assertEqual(theo['used'], 40 * 60)

    def test_combo_change_works_on_the_sign_in_screen_already_up(self):
        old = self.combo('theo')
        status, _ = self.owner_edits(lambda p: p['theo'].update(combo=['up', 'down', '3']))
        self.assertEqual(status, 200)
        self.tap(*old)
        self.assertEqual(self.sim.view, 'signin')
        self.tap('up', 'down', '3')
        self.assertEqual(self.sim.view, 'welcome')
        self.assertEqual(self.sim.state()['session']['profile'], 'theo')

    def test_hours_change_applies_at_the_next_game(self):
        self.clock.set_wall(dt.datetime(2026, 11, 27, 10, 0).timestamp())   # Fri 10 am
        self.sign_in('theo')
        self.assertEqual(self.play()['view'], 'refused')
        status, _ = self.owner_edits(
            lambda p: p['theo']['limits']['hours'].update(weekdays=['09:00-12:00', '15:00-20:00']))
        self.assertEqual(status, 200)
        self.sim.view = 'menu'
        self.tap('1')
        self.assertEqual(self.sim.view, 'game')

    def test_name_change_and_a_new_player(self):
        _, state = self.call('/api/cabinet')
        profiles = copy.deepcopy(state['profiles'])
        john = next(p for p in profiles['profiles'] if p['id'] == 'john')
        john['name'] = 'Johnny'
        profiles['profiles'].append(dict(copy.deepcopy(john), id='sam', name='Sam', combo=['3', '3', '4']))
        status, state = self.call('/api/profiles', {'profiles': profiles})
        self.assertEqual(status, 200, state)
        self.assertIn('Johnny', self.sim.state()['screen']['lines'][1])
        self.tap('3', '3', '4')
        self.assertEqual(self.sim.state()['screen']['title'], 'Signed in: Sam')

    def test_a_bad_change_is_refused_and_the_cabinet_keeps_what_it_had(self):
        before = self.settings_files()
        cases = [
            lambda p: p['theo'].update(combo=['coin', '1']),
            lambda p: p['theo'].update(combo=list(p['matt']['combo']) + ['3']),
            lambda p: p['theo']['limits']['hours'].update(weekdays='20:00-15:00'),
            lambda p: p['theo']['limits']['time'].update(minutes='ninety'),
            lambda p: p['john'].update(name='Theo'),
        ]
        for edit in cases:
            status, body = self.owner_edits(edit)
            self.assertEqual(status, 400, body)
            self.assertTrue(body['error'])
        self.assertEqual(self.settings_files(), before)

    def test_the_cabinet_checks_a_change_itself_too(self):
        state = self.cabinet().show()
        broken = copy.deepcopy(state['profiles'])
        broken['profiles'] = [p for p in broken['profiles'] if p['role'] != 'owner']
        with self.assertRaises(admin.CabinetError) as e:
            self.cabinet().write({'profiles': broken})
        self.assertIn('owner', str(e.exception))


    def remove(self, pid):
        _, state = self.call('/api/cabinet')
        profiles = copy.deepcopy(state['profiles'])
        profiles['profiles'] = [p for p in profiles['profiles'] if p['id'] != pid]
        status, state = self.call('/api/profiles', {'profiles': profiles})
        self.assertEqual(status, 200, state)

    def test_bg2_removed_on_the_welcome_screen_is_signed_out_at_once(self):
        self.sign_in('john')
        self.remove('john')
        state = self.sim.state()
        self.assertEqual(state['view'], 'signin')
        self.assertIsNone(state['session'])
        self.assertIn("John's profile was removed", state['screen']['message'])
        self.tap('1')
        self.assertEqual(self.sim.view, 'signin')
        self.tap(*self.combo('theo'))
        self.assertEqual(self.sim.view, 'welcome')

    def test_bg2_removed_at_the_game_list_cannot_start_a_game(self):
        self.sign_in('john')
        self.tap('1')
        self.remove('john')
        state = self.play_from_menu()
        self.assertEqual(state['view'], 'refused')
        self.assertIn("John's profile was removed", self.text(state))

    def test_bg2_removed_mid_game_stops_the_game(self):
        self.sign_in('john')
        self.play()
        self.clock.advance(5 * 60)
        self.sim.state()
        self.remove('john')
        state = self.sim.state()
        self.assertEqual(state['view'], 'timeup')
        self.assertIn("John's profile was removed", self.text(state))
        self.assertEqual(self.play_from_menu()['view'], 'refused')

    def play_from_menu(self):
        self.sim.view = 'menu'
        self.tap('1')
        return self.sim.state()


class FlagFromComputerTest(AdminTest):
    def exit_game(self):
        self.sim.feed('coin', True)
        self.tap('start')
        self.sim.feed('coin', False)

    def test_turning_enforcement_off_the_next_quit_goes_to_the_console(self):
        # BG-1: one quit after Turn off reaches the console, as before profiles.
        self.sign_in('theo')
        self.tap('1')
        status, state = self.call('/api/enforce', {'enforce': False})
        self.assertEqual(status, 200, state)
        self.assertFalse(state['enforce'])
        # Mid-session nothing changes (MH-4): Theo's game is still checked and counted.
        self.assertEqual(self.sim.view, 'menu')
        self.tap('1')
        self.assertEqual(self.sim.view, 'game')
        self.clock.advance(10 * 60)
        self.exit_game()
        theo = next(u for u in self.sim.state()['usage'] if u['id'] == 'theo')
        self.assertEqual(theo['used'], 10 * 60)
        self.quit_es()
        self.assertEqual(self.sim.view, 'shell')
        self.assertFalse(self.sim.state()['enforced'])

    def test_off_then_on_again_before_the_quit_stays_under_profiles(self):
        self.sign_in('matt')
        self.tap('1')
        self.call('/api/enforce', {'enforce': False})
        status, state = self.call('/api/enforce', {'enforce': True})
        self.assertTrue(state['enforce'])
        self.quit_es()
        self.assertEqual(self.sim.view, 'signin')

    def test_bad_flag_value_is_refused(self):
        status, body = self.call('/api/enforce', {'enforce': 'yes'})
        self.assertEqual(status, 400)


class FlagOffBootTest(AdminTest):
    cabinet_config = OFF_CABINET

    def test_flag_off_boot_turned_on_from_the_computer_signs_in_after_the_next_quit(self):
        self.assertEqual(self.sim.view, 'menu')
        self.call('/api/enforce', {'enforce': True})
        self.tap('1')
        self.assertEqual(self.sim.view, 'game')                  # this session stays as before
        self.sim.feed('coin', True)
        self.tap('start')
        self.sim.feed('coin', False)
        self.quit_es()
        self.assertEqual(self.sim.view, 'signin')
        self.assertTrue(self.sim.state()['enforced'])

    def test_flag_off_unchanged_still_quits_to_the_console(self):
        self.quit_es()
        self.assertEqual(self.sim.view, 'shell')


def write_exe(path, body):
    with open(path, 'w') as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


class OverSshTest(AdminTest):
    """The admin's SSH path, with a stand-in ssh that runs the remote command
    here, against the simulator's cabinet as if it were the Pi."""

    def cabinet(self):
        bindir = os.path.join(self.dir, 'bin')
        os.makedirs(bindir, exist_ok=True)
        self.ssh_log = os.path.join(self.dir, 'ssh.log')
        write_exe(os.path.join(bindir, 'ssh'),
                  '#!/bin/bash\n'
                  'while [[ "$1" == -o ]]; do shift 2; done\n'
                  'echo "$1" >> "%s"\nshift\n'
                  'export PI_ARCADE_STATE_DIR="%s"\nexec bash -c "$*"\n' % (self.ssh_log, self.dir))
        cabinet = admin.ssh_cabinet('pi@retropie.local', REPO)
        cabinet.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ['PATH'])
        return cabinet

    def test_ac8_over_ssh(self):
        status, state = self.call('/api/cabinet')
        self.assertEqual(status, 200, state)
        self.assertEqual(state['target'], 'pi@retropie.local')
        self.set_minutes('theo', 90)
        self.assertIn('Time left: 1 h 30 min', self.sign_in('theo'))
        with open(self.ssh_log) as f:
            self.assertEqual(set(f.read().split()), {'pi@retropie.local'})

    def test_unreachable_cabinet_says_so(self):
        self.httpd.cabinet.command[-1] = 'PYTHONPATH=/nowhere python3 -m arcade_profiles.settings'
        status, body = self.call('/api/cabinet')
        self.assertEqual(status, 502)
        self.assertIn('Could not reach the cabinet', body['error'])


if __name__ == '__main__':
    unittest.main()
