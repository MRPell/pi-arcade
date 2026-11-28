"""Arcade profiles M-5 (launch): before the owner turns arcade-profiles.enforce
on at the real cabinet, `make preflight` says whether the cabinet is ready for
every scenario to work there, and what to do about anything that is not.

These tests run the cabinet side (python3 -m arcade_profiles.preflight)
against a stand-in cabinet laid out in a temporary folder."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from arcade_profiles import preflight  # noqa: E402

FIXTURES = os.path.join(REPO, 'tests', 'fixtures', 'mame2003-hi')


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.configs = os.path.join(self.tmp, 'configs-all')
        os.makedirs(self.configs)
        self.state = os.path.join(self.tmp, 'state')
        os.makedirs(self.state)
        self.hi = os.path.join(self.tmp, 'mame2003', 'hi')
        shutil.copytree(FIXTURES, self.hi)
        self.font = os.path.join(self.tmp, 'font.psf.gz')
        open(self.font, 'w').close()

    def install(self):
        """What install.sh leaves on the cabinet."""
        with open(os.path.join(self.configs, 'autostart.sh'), 'w') as f:
            f.write('bash %s/scripts/arcade-session.sh #auto\n' % REPO)
        with open(os.path.join(self.configs, 'autostart.sh.pre-profiles'), 'w') as f:
            f.write('emulationstation #auto\n')
        for hook in preflight.HOOKS:
            os.symlink(os.path.join(REPO, 'scripts', hook), os.path.join(self.configs, hook))

    def run_checks(self, **kw):
        args = dict(timezone='America/Denver', cabinet_timezone='America/Denver',
                    synced=True, pad_names=['Pi Arcade Controller'], configs_dir=self.configs,
                    repo_dir=REPO, font=self.font, hi_dirs=[self.hi], state=self.state)
        args.update(kw)
        return {name: (status, detail) for status, name, detail in preflight.checks(**args)}

    def failing(self, results):
        return sorted(name for name, (status, _) in results.items() if status == preflight.FAIL)

    def test_a_ready_cabinet_passes_every_check(self):
        self.install()
        results = self.run_checks()
        self.assertEqual(self.failing(results), [])
        self.assertIn('Pac-Man 9,350', results['high scores'][1])
        self.assertIn('Space Invaders 800', results['high scores'][1])
        self.assertEqual(results['flag'], (preflight.INFO, 'arcade-profiles.enforce is off; turn it on in make admin'))

    def test_a_cabinet_not_installed_yet_says_to_run_the_installer(self):
        with open(os.path.join(self.configs, 'autostart.sh'), 'w') as f:
            f.write('emulationstation #auto\n')
        results = self.run_checks()
        self.assertEqual(self.failing(results), ['autostart', 'game hooks'])
        self.assertIn('make install', results['autostart'][1])
        self.assertIn('make install', results['game hooks'][1])

    def test_a_hook_that_is_not_ours_fails(self):
        self.install()
        hook = os.path.join(self.configs, preflight.HOOKS[0])
        os.remove(hook)
        with open(hook, 'w') as f:
            f.write('#!/bin/sh\n')
        status, detail = self.run_checks()['game hooks']
        self.assertEqual(status, preflight.FAIL)
        self.assertIn(preflight.HOOKS[0], detail)

    def test_cabinet_time_zone_must_match_the_owners(self):
        # Play hours are the cabinet's clock hours: a cabinet on London time
        # opens 3 pm to 8 pm play at 8 am Denver time.
        self.install()
        status, detail = self.run_checks(cabinet_timezone='Europe/London')['time zone']
        self.assertEqual(status, preflight.FAIL)
        self.assertIn('Europe/London', detail)
        self.assertIn('sudo timedatectl set-timezone America/Denver', detail)

    def test_clock_not_set_from_the_network_fails(self):
        self.install()
        status, detail = self.run_checks(synced=False)['clock']
        self.assertEqual(status, preflight.FAIL)
        self.assertIn('only the owner can play', detail)

    def test_no_pad_means_no_sign_in(self):
        self.install()
        status, detail = self.run_checks(pad_names=['vc4-hdmi'])['controls']
        self.assertEqual(status, preflight.FAIL)
        self.assertIn('pi-arcade-gpio', detail)

    def test_missing_console_font_fails(self):
        self.install()
        os.remove(self.font)
        self.assertEqual(self.run_checks()['sign-in font'][0], preflight.FAIL)

    def test_no_hiscore_folder_fails_and_unplayed_games_are_listed(self):
        self.install()
        status, _ = self.run_checks(hi_dirs=[os.path.join(self.tmp, 'nope')])['high scores']
        self.assertEqual(status, preflight.FAIL)
        os.remove(os.path.join(self.hi, 'galaga.hi'))
        status, detail = self.run_checks()['high scores']
        self.assertEqual(status, preflight.OK)
        self.assertIn('Galaga no save yet', detail)

    def test_owner_settings_and_flag_on_are_reported(self):
        self.install()
        with open(os.path.join(self.state, 'cabinet.json'), 'w') as f:
            json.dump({'arcade-profiles.enforce': True}, f)
        results = self.run_checks()
        self.assertEqual(results['flag'][0], preflight.INFO)
        self.assertIn('on', results['flag'][1])
        self.assertIn('Matt (owner), Theo, John, Guest', results['profiles'][1])

    def test_broken_owner_profiles_fail(self):
        self.install()
        with open(os.path.join(self.state, 'profiles.json'), 'w') as f:
            f.write('{"profiles": [')
        self.assertEqual(self.run_checks()['profiles'][0], preflight.FAIL)

    def test_command_exits_1_on_a_failure_and_prints_each_check(self):
        env = dict(os.environ, PYTHONPATH=os.path.join(REPO, 'src'), PI_ARCADE_STATE_DIR=self.state,
                   PI_ARCADE_HISCORE_DIR=self.hi)
        result = subprocess.run([sys.executable, '-m', 'arcade_profiles.preflight',
                                 '--timezone', 'Nowhere/Nope'], env=env, timeout=60,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = result.stdout.decode()
        self.assertEqual(result.returncode, 1, out + result.stderr.decode())
        self.assertIn('FAIL  time zone', out)
        self.assertIn('ok    high scores', out)


if __name__ == '__main__':
    unittest.main()
