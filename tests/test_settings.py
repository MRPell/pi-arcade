"""The cabinet's settings (arcade_profiles.settings): the owner's copy from
their computer wins over the shipped config, a bad change writes nothing, and
the cabinet's screens pick up a change while they are up (M-3)."""

import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from arcade_profiles import play, settings  # noqa: E402
from arcade_profiles.profiles import ProfileError  # noqa: E402
from arcade_profiles.usage import Ledger  # noqa: E402

with open(os.path.join(REPO, 'config', 'profiles.json')) as f:
    SHIPPED = json.load(f)
OFF = os.path.join(REPO, 'config', 'cabinet.json')


def with_minutes(pid, minutes):
    raw = copy.deepcopy(SHIPPED)
    next(p for p in raw['profiles'] if p['id'] == pid)['limits']['time']['minutes'] = minutes
    return raw


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_without_the_owners_copy_the_shipped_config_is_used(self):
        self.assertFalse(settings.enforce_on(self.dir, OFF))
        self.assertEqual(settings.load_raw_profiles(self.dir), SHIPPED)
        self.assertFalse(settings.show(self.dir, OFF)['from_admin'])

    def test_the_owners_copy_wins(self):
        settings.write({'enforce': True, 'profiles': with_minutes('theo', 90)}, self.dir)
        self.assertTrue(settings.enforce_on(self.dir, OFF))
        theo = next(p for p in settings.load_profiles(self.dir) if p.id == 'theo')
        self.assertEqual(theo.limits.minutes, 90)
        self.assertTrue(settings.show(self.dir, OFF)['from_admin'])

    def test_a_bad_change_writes_nothing(self):
        bad = copy.deepcopy(SHIPPED)
        bad['profiles'][1]['combo'] = ['coin']
        for change in ({'profiles': bad, 'enforce': True}, {'enforce': 'yes'}, {}, {'other': 1},
                       {'profiles': {'profiles': [{'id': 'x'}]}}, {'profiles': 'nope'}):
            with self.assertRaises(ValueError):
                settings.write(change, self.dir)
        self.assertEqual(os.listdir(self.dir), [])

    def test_flag_command_reads_the_owners_setting(self):
        env = dict(os.environ, PYTHONPATH=os.path.join(REPO, 'src'), PI_ARCADE_STATE_DIR=self.dir)
        flag = [sys.executable, '-m', 'arcade_profiles.flag', OFF]
        self.assertEqual(subprocess.call(flag, env=env), 1)
        settings.write({'enforce': True}, self.dir)
        self.assertEqual(subprocess.call(flag, env=env), 0)
        settings.write({'enforce': False}, self.dir)
        self.assertEqual(subprocess.call(flag, env=env), 1)

    def test_settings_command_show_and_write(self):
        env = dict(os.environ, PYTHONPATH=os.path.join(REPO, 'src'), PI_ARCADE_STATE_DIR=self.dir,
                   PI_ARCADE_CABINET_CONFIG=OFF)
        cmd = [sys.executable, '-m', 'arcade_profiles.settings']
        out = subprocess.run(cmd + ['write'], env=env, input=json.dumps({'enforce': True}).encode(),
                             stdout=subprocess.PIPE)
        self.assertEqual(out.returncode, 0)
        self.assertTrue(json.loads(out.stdout.decode())['enforce'])
        out = subprocess.run(cmd + ['write'], env=env, input=b'{"enforce": 1}', stdout=subprocess.PIPE)
        self.assertEqual(out.returncode, 1)
        self.assertIn('error', json.loads(out.stdout.decode()))
        out = subprocess.run(cmd + ['show'], env=env, stdout=subprocess.PIPE)
        self.assertTrue(json.loads(out.stdout.decode())['enforce'])

    def test_watch_picks_up_a_change_and_keeps_the_last_good_one(self):
        watch = settings.ProfilesWatch(self.dir)
        self.assertEqual(next(p for p in watch.current() if p.id == 'theo').limits.minutes, 60)
        settings.write({'profiles': with_minutes('theo', 90)}, self.dir)
        self.assertEqual(next(p for p in watch.current() if p.id == 'theo').limits.minutes, 90)
        with open(os.path.join(self.dir, settings.PROFILES), 'w') as f:
            f.write('{broken')
        self.assertEqual(next(p for p in watch.current() if p.id == 'theo').limits.minutes, 90)

    def test_check_profiles_reports_malformed_input_as_a_profile_error(self):
        for raw in ({'profiles': [{'id': 'x'}]}, {'profiles': 3}, None):
            with self.assertRaises(ProfileError):
                settings.check_profiles(raw)


class RefreshLimitTest(unittest.TestCase):
    """The guard holds a running game to the profile's limits as they are now."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.start = dt.datetime(2026, 11, 27, 16, 0).timestamp()      # Fri 4 pm
        self.ledger = Ledger(self.dir, self.start - 3600)
        self.ledger.start('theo', self.start, 0.0, 3600.0)

    def limit(self, raw, played):
        profiles = settings.check_profiles(raw)
        play.refresh_limit(profiles, self.ledger, self.start + played, played)
        return self.ledger.open['limit']

    def test_raised_limit(self):
        self.assertEqual(self.limit(with_minutes('theo', 90), 600), 90 * 60)

    def test_lowered_below_what_was_played_stops_now_and_keeps_it(self):
        self.assertEqual(self.limit(with_minutes('theo', 30), 40 * 60), 40 * 60)

    def test_hours_ending_sooner(self):
        raw = copy.deepcopy(SHIPPED)
        next(p for p in raw['profiles'] if p['id'] == 'theo')['limits']['hours']['weekdays'] = '15:00-16:30'
        self.assertEqual(self.limit(raw, 600), 30 * 60)

    def test_profile_removed_keeps_its_limit(self):
        raw = copy.deepcopy(SHIPPED)
        raw['profiles'] = [p for p in raw['profiles'] if p['id'] != 'theo']
        self.assertEqual(self.limit(raw, 600), 3600.0)


if __name__ == '__main__':
    unittest.main()
