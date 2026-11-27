"""The runcommand hooks that put games under a profile's rules on the cabinet
(arcade-profiles M-2): they do nothing unless EmulationStation was started with
enforcement on, a refused game never starts, and an allowed one is counted."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ONSTART = os.path.join(REPO, 'scripts', 'runcommand-onstart.sh')
ONEND = os.path.join(REPO, 'scripts', 'runcommand-onend.sh')
SESSION = os.path.join(REPO, 'scripts', 'arcade-session.sh')


def write_exe(path, body):
    with open(path, 'w') as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, 'state')
        self.env = dict(os.environ, PI_ARCADE_DIR=REPO, PI_ARCADE_STATE_DIR=self.state)
        self.env.pop('ARCADE_PROFILES_ENFORCED', None)
        self.launched = os.path.join(self.tmp, 'launched')
        # Stand-in for runcommand.sh: run the start hook, then "the emulator".
        self.runcommand = os.path.join(self.tmp, 'runcommand.sh')
        write_exe(self.runcommand, '#!/bin/bash\nbash "%s" nes lr-fceumm rom cmd\n'
                                   'echo game >> "%s"\nbash "%s"\n' % (ONSTART, self.launched, ONEND))

    def run_runcommand(self, **env):
        return subprocess.run([self.runcommand], env=dict(self.env, **env), timeout=30,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def sign_in(self, pid):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, 'session.json'), 'w') as f:
            json.dump({'profile': pid}, f)

    def test_not_enforced_games_start_as_before_and_nothing_is_counted(self):
        result = self.run_runcommand()
        self.assertEqual(result.returncode, 0)
        with open(self.launched) as f:
            self.assertEqual(f.read(), 'game\n')
        self.assertFalse(os.path.exists(self.state))

    def test_enforced_with_nobody_signed_in_the_game_never_starts(self):
        result = self.run_runcommand(ARCADE_PROFILES_ENFORCED='1')
        self.assertEqual(result.returncode, -15, result.stderr.decode())   # runcommand ended
        self.assertFalse(os.path.exists(self.launched))

    def test_enforced_owner_game_starts_and_is_counted(self):
        self.sign_in('matt')
        result = self.run_runcommand(ARCADE_PROFILES_ENFORCED='1')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(os.path.exists(self.launched))
        with open(os.path.join(self.state, 'usage.json')) as f:
            usage = json.load(f)
        self.assertIsNone(usage['open'])
        self.assertEqual([p['profile'] for p in usage['plays']], ['matt'])

    def test_start_runs_a_guard_and_end_stops_it(self):
        self.sign_in('matt')
        env = dict(self.env, PYTHONPATH=os.path.join(REPO, 'src'))
        gate = [sys.executable, '-m', 'arcade_profiles.gate_console']
        self.assertEqual(subprocess.call(gate + ['start', str(os.getpid())], env=env), 0)
        with open(os.path.join(self.state, 'usage.json')) as f:
            guard = json.load(f)['open']['guard']
        os.kill(guard, 0)                        # running
        self.assertEqual(subprocess.call(gate + ['end'], env=env), 0)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(guard, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail('guard still running after end')


@unittest.skipUnless(os.path.isdir('/proc/self'), 'needs Linux /proc (run on the Pi)')
class StopGameTest(unittest.TestCase):
    def test_time_up_ends_everything_runcommand_started_and_runcommand_carries_on(self):
        sys.path.insert(0, os.path.join(REPO, 'src'))
        from arcade_profiles.gate_console import stop_game
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        after = os.path.join(tmp, 'after')
        # runcommand stand-in: a game with a child of its own, then the end hook's turn.
        rc = subprocess.Popen(['bash', '-c', 'bash -c "sleep 600 & wait"; echo onend > "%s"' % after])
        time.sleep(0.5)
        stop_game(rc.pid)
        self.assertEqual(rc.wait(timeout=10), 0)
        self.assertTrue(os.path.exists(after))


class SessionEnvTest(unittest.TestCase):
    def test_flag_off_emulationstation_is_not_enforced(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        calls = os.path.join(tmp, 'calls')
        bindir = os.path.join(tmp, 'bin')
        os.mkdir(bindir)
        write_exe(os.path.join(bindir, 'emulationstation'),
                  '#!/bin/sh\necho "enforced=$ARCADE_PROFILES_ENFORCED" >> "%s"\n' % calls)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ['PATH'], PI_ARCADE_DIR=REPO,
                   PI_ARCADE_CABINET_CONFIG=os.path.join(REPO, 'config', 'cabinet.json'))
        env.pop('ARCADE_PROFILES_ENFORCED', None)
        subprocess.run(['bash', SESSION], env=env, timeout=20)
        with open(calls) as f:
            self.assertEqual(f.read(), 'enforced=\n')


if __name__ == '__main__':
    unittest.main()
