"""Drawing on the cabinet's text console and reading its pad, for the screens
shown outside EmulationStation (sign-in, play refused, time up)."""

import json
import os
import select
import shutil
import sys
import time

from .pad import PadDecoder, input_codes
from .settings import REPO_DIR
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


def clear():
    sys.stdout.write('\033[H\033[2J\033[?25h')
    sys.stdout.flush()


def open_pad(wait=PAD_WAIT_SECONDS):
    """The panel's pad and a decoder for it, or (None, None) if it never shows up."""
    import evdev
    from evdev import ecodes

    with open(os.path.join(REPO_DIR, 'config', 'gpio_map.json')) as f:
        gpio_map = json.load(f)
    deadline = time.monotonic() + wait
    while True:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name == PAD_NAME:
                decoder = PadDecoder(input_codes(gpio_map, lambda name: getattr(ecodes, name)),
                                     ecodes.ABS_X, ecodes.ABS_Y)
                return dev, decoder
        if time.monotonic() >= deadline:
            return None, None
        time.sleep(1)


def show_until_button(screen, seconds, grace):
    """Draw screen, then wait up to seconds, or for a button pressed after grace."""
    draw(screen)
    pad, decoder = open_pad(wait=0)
    start = time.monotonic()
    try:
        while True:
            left = seconds - (time.monotonic() - start)
            if left <= 0:
                return
            if pad is None:
                time.sleep(left)
                return
            ready, _, _ = select.select([pad], [], [], left)
            if not ready:
                continue
            for event in pad.read():
                pressed = [p for _, p in decoder.feed(event.type, event.code, event.value) if p]
                if pressed and time.monotonic() - start >= grace:
                    return
    finally:
        clear()
