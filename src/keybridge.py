#!/usr/bin/env python3
"""
Pi Arcade key bridge

Launches a keyboard-only game (an EmulationStation "port") and, while it runs,
translates the Pi Arcade Controller's virtual gamepad into keyboard keys on a
virtual uinput keyboard. Holding the keymap's exit chord (Coin + Start, same as
RetroArch) ends the game.

Usage: keybridge.py KEYMAP.json -- COMMAND [ARGS...]

Keymap format:
    {
      "buttons":    {"BTN_SOUTH": "KEY_SPACE", ...},
      "axes":       {"left": "KEY_LEFT", "right": "KEY_RIGHT", "up": "KEY_UP", "down": "KEY_DOWN"},
      "exit_chord": ["BTN_SELECT", "BTN_START"]
    }
"""

import json
import select
import signal
import subprocess
import sys
import time

from evdev import InputDevice, UInput, ecodes as e, list_devices

PAD_NAME = 'Pi Arcade Controller'

# ABS axis -> (direction when negative, direction when positive)
AXIS_DIRECTIONS = {
    e.ABS_X: ('left', 'right'),
    e.ABS_Y: ('up', 'down'),
}


class Translator:
    """Pure gamepad-event -> key-event mapping, kept free of I/O for testing."""

    def __init__(self, keymap):
        self._buttons = {e.ecodes[b]: e.ecodes[k] for b, k in keymap.get('buttons', {}).items()}
        self._axes = {d: e.ecodes[k] for d, k in keymap.get('axes', {}).items()}
        self._chord = {e.ecodes[b] for b in keymap.get('exit_chord', [])}
        self._held = set()
        self._axis_dir = {}  # ABS code -> currently pressed direction name or None
        self.exit_requested = False

    def output_keys(self):
        return sorted(set(self._buttons.values()) | set(self._axes.values()))

    def feed(self, ev_type, code, value):
        if ev_type == e.EV_KEY:
            return self._feed_button(code, value)
        if ev_type == e.EV_ABS and code in AXIS_DIRECTIONS:
            return self._feed_axis(code, value)
        return []

    def _feed_button(self, code, value):
        if value:
            self._held.add(code)
        else:
            self._held.discard(code)
        if self._chord and self._chord <= self._held:
            self.exit_requested = True
        key = self._buttons.get(code)
        if key is None or value == 2:  # ignore autorepeat
            return []
        return [(key, 1 if value else 0)]

    def _feed_axis(self, code, value):
        neg, pos = AXIS_DIRECTIONS[code]
        new = neg if value < 0 else pos if value > 0 else None
        old = self._axis_dir.get(code)
        if new == old:
            return []
        self._axis_dir[code] = new
        out = []
        if old in self._axes:
            out.append((self._axes[old], 0))
        if new in self._axes:
            out.append((self._axes[new], 1))
        return out


def find_pad():
    for path in list_devices():
        dev = InputDevice(path)
        if dev.name == PAD_NAME:
            return dev
    return None


def main(argv):
    if len(argv) < 4 or argv[2] != '--':
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        translator = Translator(json.load(f))
    command = argv[3:]

    pad = find_pad()
    if pad is None:
        print('keybridge: %r not found, running without it' % PAD_NAME, file=sys.stderr)
        return subprocess.call(command)

    kbd = UInput({e.EV_KEY: translator.output_keys()}, name='Pi Arcade Keys')
    # Give the kernel a moment to announce the new keyboard before the game
    # opens its input devices, or SDL may start without it.
    time.sleep(0.5)
    child = subprocess.Popen(command)
    signal.signal(signal.SIGTERM, lambda *_: child.terminate())

    try:
        while child.poll() is None:
            ready, _, _ = select.select([pad], [], [], 0.2)
            if not ready:
                continue
            for event in pad.read():
                keys = translator.feed(event.type, event.code, event.value)
                for key, value in keys:
                    kbd.write(e.EV_KEY, key, value)
                if keys:
                    kbd.syn()
            if translator.exit_requested:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
    finally:
        for key in translator.output_keys():
            kbd.write(e.EV_KEY, key, 0)
        kbd.syn()
        kbd.close()
    return child.wait()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
