"""scripts/arcade-session.sh, which RetroPie's autostart runs in place of
`emulationstation`. With arcade-profiles.enforce off it must start
EmulationStation exactly as before and never show sign-in."""

import json
import os
import stat
import subprocess
import tempfile
import shutil
import time
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


class ArcadeSessionFlagChangeTest(unittest.TestCase):
    """M-3: the owner turns the flag on or off from their computer and the
    cabinet follows at the next EmulationStation quit, with no restart."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, 'state')
        os.mkdir(self.state)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        self.calls = os.path.join(self.tmp, 'calls')
        # Stand-in EmulationStation: records each launch and whether it was
        # under profiles. On its first run the owner turns the flag on.
        fake_es = os.path.join(bindir, 'emulationstation')
        with open(fake_es, 'w') as f:
            f.write('#!/bin/bash\n'
                    'echo "es enforced=${ARCADE_PROFILES_ENFORCED:-0}" >> "%s"\n'
                    'if [[ $(wc -l < "%s") -eq 1 ]]; then\n'
                    '  echo \'{"arcade-profiles.enforce": true}\' > "%s/cabinet.json"\n'
                    'fi\n'
                    'exit 7\n' % (self.calls, self.calls, self.state))
        os.chmod(fake_es, os.stat(fake_es).st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ['PATH'],
                        PI_ARCADE_DIR=REPO, PI_ARCADE_STATE_DIR=self.state,
                        PI_ARCADE_CABINET_CONFIG=os.path.join(REPO, 'config', 'cabinet.json'))
        self.env.pop('ARCADE_PROFILES_ENFORCED', None)

    def test_turned_on_while_running_signs_in_at_the_next_quit_then_off_again(self):
        proc = subprocess.Popen(['bash', SCRIPT], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Sign-in has no pad here, so it fails and retries every 3 seconds;
        # the owner then turns the flag off again.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not os.path.exists(os.path.join(self.state, 'cabinet.json')):
            time.sleep(0.1)
        time.sleep(1.5)
        with open(os.path.join(self.state, 'cabinet.json'), 'w') as f:
            json.dump({'arcade-profiles.enforce': False}, f)
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, 7)
        self.assertIn(b'Sign-in failed; retrying', err)       # sign-in ran after the quit
        with open(self.calls) as f:
            self.assertEqual(f.read().splitlines(), ['es enforced=0', 'es enforced=0'])


class ArcadeSessionTurnedOffTest(unittest.TestCase):
    """BG-1: flag on, the owner turns it off while EmulationStation runs, and
    the next quit goes to the console, as before profiles: one quit, not two."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, 'state')
        os.mkdir(self.state)
        with open(os.path.join(self.state, 'cabinet.json'), 'w') as f:
            json.dump({'arcade-profiles.enforce': True}, f)
        # The cabinet's code, with a sign-in that succeeds at once (no pad here).
        repo = os.path.join(self.tmp, 'repo')
        shutil.copytree(os.path.join(REPO, 'src'), os.path.join(repo, 'src'))
        shutil.copytree(os.path.join(REPO, 'config'), os.path.join(repo, 'config'))
        with open(os.path.join(repo, 'src', 'arcade_profiles', 'signin_console.py'), 'w') as f:
            f.write('import sys\nsys.exit(0)\n')
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        self.calls = os.path.join(self.tmp, 'calls')
        fake_es = os.path.join(bindir, 'emulationstation')
        with open(fake_es, 'w') as f:
            f.write('#!/bin/bash\n'
                    'echo "es enforced=${ARCADE_PROFILES_ENFORCED:-0}" >> "%s"\n'
                    'echo \'{"arcade-profiles.enforce": false}\' > "%s/cabinet.json"\n'
                    'exit 7\n' % (self.calls, self.state))
        os.chmod(fake_es, os.stat(fake_es).st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ['PATH'],
                        PI_ARCADE_DIR=repo, PI_ARCADE_STATE_DIR=self.state,
                        PI_ARCADE_CABINET_CONFIG=os.path.join(repo, 'config', 'cabinet.json'))
        self.env.pop('ARCADE_PROFILES_ENFORCED', None)

    def test_turned_off_while_running_the_next_quit_goes_to_the_console(self):
        result = subprocess.run(['bash', SCRIPT], env=self.env, timeout=20,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 7, result.stderr.decode())
        with open(self.calls) as f:
            self.assertEqual(f.read().splitlines(), ['es enforced=1'])


if __name__ == '__main__':
    unittest.main()
