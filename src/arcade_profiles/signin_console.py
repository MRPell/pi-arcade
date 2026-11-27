"""The cabinet's sign-in screen, drawn on the text console before EmulationStation.

Run by scripts/arcade-session.sh when arcade-profiles.enforce is on. Reads the
Pi Arcade Controller pad, shows the sign-in screen, records who signed in in
the session file, and exits 0 once they press a button to play.

Usage: python3 -m arcade_profiles.signin_console
"""

import json
import os
import select
import shutil
import sys
import time

from .pad import PadDecoder, input_codes
from .profiles import load_profiles
from .session import clear_session, state_dir, write_session
from .signin import SignIn

REPO_DIR = os.environ.get(
    'PI_ARCADE_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
PAD_NAME = 'Pi Arcade Controller'
PAD_WAIT_SECONDS = 30


def render(screen, columns, rows):
    """The screen as console lines, centred in a columns x rows terminal."""
    lines = [screen['title'], '']
    if screen['view'] == 'signin':
        lines.append(' '.join(['*'] * screen['entered']) or '-')
        lines.append(screen['message'] or '')
        lines.append('')
    lines += screen['lines']
    top = max(0, (rows - len(lines)) // 2)
    return [''] * top + [line.center(columns).rstrip() for line in lines]


def draw(screen):
    size = shutil.get_terminal_size((80, 24))
    out = '\033[H\033[2J\033[?25l' + '\n'.join(render(screen, size.columns, size.lines))
    sys.stdout.write(out)
    sys.stdout.flush()


def find_pad(evdev):
    deadline = time.monotonic() + PAD_WAIT_SECONDS
    while time.monotonic() < deadline:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name == PAD_NAME:
                return dev
        time.sleep(1)
    return None


def main():
    import evdev
    from evdev import ecodes

    profiles = load_profiles(os.path.join(REPO_DIR, 'config', 'profiles.json'))
    with open(os.path.join(REPO_DIR, 'config', 'gpio_map.json')) as f:
        gpio_map = json.load(f)
    directory = state_dir()
    clear_session(directory)

    pad = find_pad(evdev)
    if pad is None:
        print('sign-in: %r not found; is pi-arcade-gpio running?' % PAD_NAME, file=sys.stderr)
        return 1
    decoder = PadDecoder(input_codes(gpio_map, lambda name: getattr(ecodes, name)),
                         ecodes.ABS_X, ecodes.ABS_Y)

    signin = SignIn(profiles, time.monotonic())
    shown = None
    try:
        while not signin.done:
            now = time.monotonic()
            signin.tick(now)
            screen = signin.screen()
            if screen != shown:
                draw(screen)
                shown = screen
            ready, _, _ = select.select([pad], [], [], 0.2)
            if not ready:
                continue
            for event in pad.read():
                for name, pressed in decoder.feed(event.type, event.code, event.value):
                    was_signed_in = signin.signed_in
                    signin.feed(name, pressed, time.monotonic())
                    if was_signed_in is None and signin.signed_in is not None:
                        write_session(directory, signin.signed_in)
    finally:
        sys.stdout.write('\033[H\033[2J\033[?25h')
        sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
