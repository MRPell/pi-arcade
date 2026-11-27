"""Games under a profile's rules on the cabinet: runcommand's start and end hooks.

    python3 -m arcade_profiles.gate_console start RUNCOMMAND_PID
        Before a game: exit 0 to let it start (and count it), or show why it
        is refused and exit 1 (runcommand-onstart.sh then ends runcommand).
    python3 -m arcade_profiles.gate_console end
        After a game: stop counting; if the game was stopped because its time
        ran out, say so.
    python3 -m arcade_profiles.gate_console guard START_MONO
        Started by `start`, detached: records the game's time as it goes and
        stops the game (everything runcommand started) when its time is up.

Only run while arcade-profiles.enforce is on (ARCADE_PROFILES_ENFORCED=1).
"""

import os
import signal
import subprocess
import sys
import time

from . import play
from .console import REPO_DIR, show_until_button
from .profiles import load_profiles
from .session import read_session, state_dir
from .usage import boot_id, locked

HEARTBEAT_SECONDS = 15.0
DISMISS_GRACE = 1.5
KILL_WAIT_SECONDS = 5.0


def _profiles():
    return load_profiles(os.path.join(REPO_DIR, 'config', 'profiles.json'))


def start(runcommand_pid):
    profiles = _profiles()
    directory = state_dir()
    session = read_session(directory)
    profile = next((p for p in profiles if session and p.id == session['profile']), None)
    if profile is None:
        show_until_button({'view': 'refused', 'title': 'Nobody is signed in',
                           'lines': ['Quit EmulationStation (Start, Quit) to sign in.',
                                     '', 'The game did not start.', 'Press any button']},
                          play.DISMISS_SECONDS, DISMISS_GRACE)
        return 1

    synced = play.network_time_synced()
    with locked(directory) as ledger:
        ledger.recover(boot_id())
        wall = time.time()
        decision = play.check(profiles, profile, wall, ledger, synced)
        if decision.allowed:
            mono = time.monotonic()
            ledger.start(profile.id, wall, mono, play.play_seconds(decision, wall), boot_id(),
                         runcommand=runcommand_pid)
    if not decision.allowed:
        show_until_button(play.refusal_screen(profiles, decision, wall),
                          play.DISMISS_SECONDS, DISMISS_GRACE)
        return 1

    env = dict(os.environ, PYTHONPATH=os.path.join(REPO_DIR, 'src'))
    guard = subprocess.Popen([sys.executable, '-m', 'arcade_profiles.gate_console', 'guard', repr(mono)],
                             env=env, start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with locked(directory) as ledger:
        if ledger.open and ledger.open['start_mono'] == mono:
            ledger.open['guard'] = guard.pid
            ledger.save()
    return 0


def _children():
    """{pid: [child pids]} from /proc."""
    out = {}
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        try:
            with open('/proc/%s/stat' % name) as f:
                stat = f.read()
        except OSError:
            continue
        ppid = int(stat.rsplit(')', 1)[1].split()[1])
        out.setdefault(ppid, []).append(int(name))
    return out


def stop_game(runcommand_pid):
    """End everything runcommand started (the emulator, or keybridge and its port),
    so runcommand carries on to its end hook and back to EmulationStation."""
    tree = _children()
    pids, todo = [], list(tree.get(runcommand_pid, []))
    while todo:
        pid = todo.pop()
        pids.append(pid)
        todo.extend(tree.get(pid, []))
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + KILL_WAIT_SECONDS
        while time.monotonic() < deadline and any(os.path.exists('/proc/%d' % p) for p in pids):
            time.sleep(0.2)


def guard(start_mono):
    directory = state_dir()
    while True:
        with locked(directory) as ledger:
            o = ledger.open
            if not o or o['start_mono'] != start_mono:
                return 0
            if ledger.heartbeat(time.monotonic()):
                ledger.mark_ended('time')
                runcommand = o['runcommand']
                break
            left = None if o['limit'] is None else o['limit'] - (time.monotonic() - start_mono)
        time.sleep(HEARTBEAT_SECONDS if left is None else max(0.2, min(HEARTBEAT_SECONDS, left)))
    stop_game(runcommand)
    return 0


def end():
    profiles = _profiles()
    with locked(state_dir()) as ledger:
        o = ledger.open
        if not o:
            return 0
        if o.get('guard'):
            try:
                os.kill(o['guard'], signal.SIGTERM)
            except ProcessLookupError:
                pass
        ended = ledger.finish(time.monotonic())
        profile = next((p for p in profiles if p.id == ended['profile']), None)
        screen = None
        if ended['ended'] == 'time' and profile is not None:
            screen = play.timeup_screen(profiles, profile, ledger, time.time(),
                                        play.network_time_synced())
    if screen:
        show_until_button(screen, play.DISMISS_SECONDS, DISMISS_GRACE)
    return 0


def main(argv):
    if len(argv) == 2 and argv[0] == 'start':
        return start(int(argv[1]))
    if len(argv) == 2 and argv[0] == 'guard':
        return guard(float(argv[1]))
    if argv == ['end']:
        return end()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
