"""scripts/arcade-session.sh, which RetroPie's autostart runs in place of
`emulationstation`. With arcade-profiles.enforce off it must start
EmulationStation exactly as before and never show sign-in."""

import json
import os
import stat
import subprocess
import tempfile
import shutil
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT = os.path.join(REPO, 'scripts', 'arcade-session.sh')


class ArcadeSessionFlagOffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        self.calls = os.path.join(self.tmp, 'calls')
        # Stand-in for the EmulationStation binary: records each launch.
        fake_es = os.path.join(bindir, 'emulationstation')
        with open(fake_es, 'w') as f:
            f.write('#!/bin/sh\necho "es $*" >> "%s"\nexit 7\n' % self.calls)
        os.chmod(fake_es, os.stat(fake_es).st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ['PATH'],
                        PI_ARCADE_DIR=REPO,
                        PI_ARCADE_STATE_DIR=os.path.join(self.tmp, 'state'))

    def run_session(self, cabinet_config):
        env = dict(self.env, PI_ARCADE_CABINET_CONFIG=cabinet_config)
        return subprocess.run(['bash', SCRIPT], env=env, timeout=20,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_flag_off_runs_emulationstation_once_and_exits_with_it(self):
        result = self.run_session(os.path.join(REPO, 'config', 'cabinet.json'))
        self.assertEqual(result.returncode, 7)
        with open(self.calls) as f:
            self.assertEqual(f.read().splitlines(), ['es '])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'state', 'session.json')))

    def test_missing_cabinet_config_counts_as_off(self):
        result = self.run_session(os.path.join(self.tmp, 'nope.json'))
        self.assertEqual(result.returncode, 7)

    def test_flag_module_exit_code(self):
        on = os.path.join(self.tmp, 'on.json')
        with open(on, 'w') as f:
            json.dump({'arcade-profiles.enforce': True}, f)
        env = dict(self.env, PYTHONPATH=os.path.join(REPO, 'src'))
        self.assertEqual(subprocess.call(['python3', '-m', 'arcade_profiles.flag', on], env=env), 0)
        off = os.path.join(REPO, 'config', 'cabinet.json')
        self.assertEqual(subprocess.call(['python3', '-m', 'arcade_profiles.flag', off], env=env), 1)


if __name__ == '__main__':
    unittest.main()
