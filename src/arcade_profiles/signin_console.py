"""The cabinet's sign-in screen, drawn on the text console before EmulationStation.

Run by scripts/arcade-session.sh when arcade-profiles.enforce is on. Reads the
Pi Arcade Controller pad, shows the sign-in screen, records who signed in in
the session file, and exits 0 once they press a button to play.

Usage: python3 -m arcade_profiles.signin_console
"""

import select
import sys
import time

from . import play
from .console import PAD_NAME, clear, draw, open_pad
from .session import clear_session, state_dir, write_session
from .settings import ProfilesWatch
from .signin import SignIn
from .usage import boot_id, locked


def main():
    watch = ProfilesWatch()
    watch.current()
    directory = state_dir()
    clear_session(directory)

    pad, decoder = open_pad()
    if pad is None:
        print('sign-in: %r not found; is pi-arcade-gpio running?' % PAD_NAME, file=sys.stderr)
        return 1

    def describe(profile):
        profiles = watch.current()
        synced = play.network_time_synced()
        with locked(directory) as ledger:
            ledger.recover(boot_id())
            wall = time.time()
            decision = play.check(profiles, profile, wall, ledger, synced)
        return play.status_lines(profiles, decision, wall)

    signin = SignIn(watch.profiles, time.monotonic(), describe)
    shown = None
    try:
        while not signin.done:
            now = time.monotonic()
            was_signed_in = signin.signed_in
            signin.update_profiles(watch.current(), now)
            if was_signed_in is not None and signin.signed_in is None:
                clear_session(directory)     # the owner removed this profile
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
        clear()
    return 0


if __name__ == '__main__':
    sys.exit(main())
