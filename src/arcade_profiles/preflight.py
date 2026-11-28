"""Is the cabinet ready for arcade-profiles.enforce to go on? (M-5, launch)

Run on the cabinet by `make preflight` from the owner's computer. Reads only:
it changes nothing. Prints one line per check, `ok`, `FAIL` (with what to do)
or `info`, and exits 1 if any check fails.

Usage: python3 -m arcade_profiles.preflight --timezone <owner's time zone>
"""

import argparse
import os
import subprocess
import sys

from . import play, scores
from .console import PAD_NAME
from .profiles import ProfileError
from .session import state_dir
from .settings import REPO_DIR, enforce_on, load_raw_profiles, check_profiles

OK, FAIL, INFO = 'ok', 'FAIL', 'info'
CONFIGS_DIR = '/opt/retropie/configs/all'
HOOKS = ('runcommand-onstart.sh', 'runcommand-onend.sh')
CONSOLE_FONT = '/usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz'


def _autostart(configs_dir):
    path = os.path.join(configs_dir, 'autostart.sh')
    try:
        with open(path) as f:
            hooked = 'arcade-session.sh' in f.read()
    except OSError:
        return FAIL, '%s is missing' % path
    if not hooked:
        return FAIL, 'EmulationStation does not start through arcade-session.sh; run make install'
    return OK, 'EmulationStation starts through arcade-session.sh'


def _hooks(configs_dir, repo_dir):
    wrong = []
    for hook in HOOKS:
        path = os.path.join(configs_dir, hook)
        target = os.path.join(repo_dir, 'scripts', hook)
        if not (os.path.islink(path) and os.path.realpath(path) == os.path.realpath(target)):
            wrong.append(hook)
    if wrong:
        return FAIL, ('%s not linked to %s/scripts; run make install (a hook of your own '
                      'there must be moved aside first)' % (', '.join(wrong), repo_dir))
    return OK, 'runcommand checks every game before and after it runs'


def _controls(pad_names):
    if PAD_NAME in pad_names:
        return OK, '%r found' % PAD_NAME
    return FAIL, '%r not found, so nobody can sign in; is pi-arcade-gpio running? (make status)' % PAD_NAME


def _font(font):
    if os.path.exists(font):
        return OK, os.path.basename(font)
    return FAIL, '%s missing: sign-in will be in the small console font' % font


def _clock(synced):
    if synced:
        return OK, 'set from the network'
    return FAIL, 'not set from the network yet: only the owner can play until it is'


def _time_zone(cabinet_timezone, timezone):
    if cabinet_timezone == timezone:
        return OK, cabinet_timezone
    return FAIL, ('cabinet is on %s, this computer on %s, so play hours are counted in the wrong '
                  'time zone; fix: ssh to the cabinet and run sudo timedatectl set-timezone %s'
                  % (cabinet_timezone or 'an unknown time zone', timezone, timezone))


def _high_scores(hi_dirs):
    if not any(os.path.isdir(d) for d in hi_dirs):
        return FAIL, 'no MAME hiscore folder (%s): play a MAME game once' % ', '.join(hi_dirs)
    parts = []
    for game in sorted(scores.load_games().values(), key=lambda g: g.title):
        found = [p for p in (scores.save_path(game, d) for d in hi_dirs) if p]
        if not found:
            parts.append('%s no save yet' % game.title)
            continue
        top = scores.read_top(game, os.path.dirname(max(found, key=os.path.getmtime)))
        parts.append('%s %s' % (game.title, 'unreadable' if top is None else scores.score_text(top)))
    return OK, '; '.join(parts)


def _profiles(state):
    try:
        profiles = check_profiles(load_raw_profiles(state))
    except (OSError, ValueError, ProfileError) as e:
        return FAIL, 'profiles cannot be read (%s): fix them in make admin' % e
    names = ['%s (owner)' % p.name if p.role == 'owner' else p.name for p in profiles]
    return OK, ', '.join(names)


def _flag(state):
    if enforce_on(state):
        return INFO, 'arcade-profiles.enforce is on; it applies from the next EmulationStation quit'
    return INFO, 'arcade-profiles.enforce is off; turn it on in make admin'


def checks(timezone, cabinet_timezone, synced, pad_names, configs_dir, repo_dir, font, hi_dirs, state):
    """[(status, name, detail)] for every launch check."""
    results = [
        ('autostart', _autostart(configs_dir)),
        ('game hooks', _hooks(configs_dir, repo_dir)),
        ('controls', _controls(pad_names)),
        ('sign-in font', _font(font)),
        ('clock', _clock(synced)),
        ('time zone', _time_zone(cabinet_timezone, timezone)),
        ('high scores', _high_scores(hi_dirs)),
        ('profiles', _profiles(state)),
        ('flag', _flag(state)),
    ]
    return [(status, name, detail) for name, (status, detail) in results]


def cabinet_time_zone():
    try:
        out = subprocess.run(['timedatectl', 'show', '-p', 'Timezone', '--value'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
        return out.stdout.decode().strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def pad_names():
    try:
        import evdev
    except ImportError:
        return []
    names = []
    for path in evdev.list_devices():
        try:
            names.append(evdev.InputDevice(path).name)
        except OSError:
            pass
    return names


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--timezone', required=True, help="the owner's time zone, e.g. America/Denver")
    args = parser.parse_args(argv)
    results = checks(args.timezone, cabinet_time_zone(), play.network_time_synced(), pad_names(),
                     CONFIGS_DIR, REPO_DIR, CONSOLE_FONT, scores.hi_dirs(), state_dir())
    for status, name, detail in results:
        print('%-5s %s: %s' % (status, name, detail))
    return 1 if any(status == FAIL for status, _, _ in results) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
