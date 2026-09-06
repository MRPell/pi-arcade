#!/usr/bin/env python3
"""
Pi Arcade GPIO Daemon

Reads GPIO inputs (joystick + buttons) and publishes them as a virtual
gamepad via Linux uinput. RetroArch/MAME see a standard gamepad device.

Config: ../config/gpio_map.json
Requires: RPi.GPIO, python3-evdev
Run as root (uinput access): sudo python3 gpio_daemon.py

Inputs are read with a tight polling loop rather than GPIO.add_event_detect:
RPi.GPIO edge callbacks silently drop edges under CPU load, which strands the
virtual axis or a button in the held state. Polling every POLL_INTERVAL and
debouncing on elapsed stable time cannot miss a transition.
"""

import json
import os
import signal
import sys
import time

import RPi.GPIO as GPIO
from evdev import UInput, ecodes as e, AbsInfo

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'gpio_map.json')

# Seconds between full sweeps of every pin. 1 ms is ~1000 Hz; each read is a
# cheap C call, so the loop costs well under 1% CPU on a Pi 3.
POLL_INTERVAL = 0.001

# Virtual gamepad capabilities exposed to the OS.
# Joystick axes: ABS_X (left/right) and ABS_Y (up/down), range -1..1.
# Buttons: BTN_SOUTH (fire), BTN_EAST (action2), BTN_NORTH (action3),
# BTN_WEST (action4), BTN_TL (action5), BTN_TR (action6), BTN_SELECT (coin), BTN_START (start).
GAMEPAD_CAPS = {
    e.EV_KEY: [
        e.BTN_SOUTH,    # fire / primary action
        e.BTN_EAST,     # secondary action
        e.BTN_NORTH,    # tertiary action
        e.BTN_WEST,     # quaternary action
        e.BTN_TL,       # fifth action / L shoulder
        e.BTN_TR,       # sixth action / R shoulder
        e.BTN_SELECT,   # coin insert
        e.BTN_START,    # player 1 start
    ],
    e.EV_ABS: [
        (e.ABS_X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (e.ABS_Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
}

# Player-2 virtual gamepad. Exists only to give MAME a port-2 Start input for
# alternating two-player games; a chord with "device": 2 is emitted here so
# MAME reads it as 2-Player Start. Created only when a chord needs it.
GAMEPAD2_CAPS = {
    e.EV_KEY: [e.BTN_SOUTH, e.BTN_START],
}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


class ArcadeInput:
    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.debounce_s = config.get('debounce_ms', 15) / 1000.0
        self._joy_state = {'up': False, 'down': False, 'left': False, 'right': False}
        self._axis = {'x': 0, 'y': 0}

        # Per-pin debounce bookkeeping.
        #   stable   – last debounced logical state (True = pressed)
        #   pending  – most recent raw reading not yet accepted
        #   since    – monotonic time the raw reading last flipped
        self._pins = []          # list of dicts: pin, kind, name, evdev_key
        self._stable = {}
        self._pending = {}
        self._since = {}
        self._chords = []        # list of dicts: name, pins, key_code, ui, active

        self.ui = UInput(GAMEPAD_CAPS, name='Pi Arcade Controller', version=0x1)
        self._log(f"Virtual gamepad created: {self.ui.device.path}")

        self.ui2 = None          # created lazily if a chord targets device 2

        self._setup_gpio()
        self._setup_chords()

    def _log(self, msg):
        if self.verbose:
            print(f"[gpio_daemon] {msg}", flush=True)

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        now = time.monotonic()

        for direction, pin in self.config['joystick'].items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._pins.append({'pin': pin, 'kind': 'joy', 'name': direction})
            self._stable[pin] = self._pending[pin] = False
            self._since[pin] = now
            self._log(f"  joystick {direction:5s} → GPIO {pin}")

        for name, cfg in self.config['buttons'].items():
            pin = cfg['gpio']
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._pins.append({
                'pin': pin, 'kind': 'button',
                'name': name, 'evdev_key': cfg['evdev_key'],
            })
            self._stable[pin] = self._pending[pin] = False
            self._since[pin] = now
            self._log(f"  button   {name:12s} → GPIO {pin}")

    def _setup_chords(self):
        buttons = self.config['buttons']
        for name, cfg in self.config.get('chords', {}).items():
            pins = [buttons[b]['gpio'] for b in cfg['buttons']]
            if cfg.get('device') == 2:
                if self.ui2 is None:
                    self.ui2 = UInput(GAMEPAD2_CAPS, name='Pi Arcade Controller P2', version=0x1)
                    self._log(f"Virtual gamepad 2 created: {self.ui2.device.path}")
                ui = self.ui2
            else:
                ui = self.ui
            self._chords.append({
                'name': name,
                'pins': pins,
                'key_code': getattr(e, cfg['evdev_key']),
                'ui': ui,
                'active': False,
            })
            self._log(f"  chord    {name:12s} ← {' + '.join(cfg['buttons'])}")

    # ------------------------------------------------------------------ #

    def poll_forever(self):
        while True:
            self._poll_once(time.monotonic())
            time.sleep(POLL_INTERVAL)

    def _poll_once(self, now):
        dirty = False
        for spec in self._pins:
            pin = spec['pin']
            pressed = GPIO.input(pin) == 0  # active-low: LOW = pressed

            if pressed != self._pending[pin]:
                self._pending[pin] = pressed
                self._since[pin] = now
                continue

            if pressed == self._stable[pin]:
                continue

            if now - self._since[pin] < self.debounce_s:
                continue

            self._stable[pin] = pressed
            if spec['kind'] == 'joy':
                self._joy_state[spec['name']] = pressed
                dirty = True
            else:
                self._emit_button(spec, pressed)

        if dirty:
            self._emit_axes()

        self._eval_chords()

    def _eval_chords(self):
        for chord in self._chords:
            held = all(self._stable[p] for p in chord['pins'])
            if held and not chord['active']:
                chord['active'] = True
                chord['ui'].write(e.EV_KEY, chord['key_code'], 1)
                chord['ui'].syn()
                self._log(f"chord {chord['name']} ↓")
            elif not held and chord['active']:
                chord['active'] = False
                chord['ui'].write(e.EV_KEY, chord['key_code'], 0)
                chord['ui'].syn()
                self._log(f"chord {chord['name']} ↑")

    def _emit_axes(self):
        x = int(self._joy_state['right']) - int(self._joy_state['left'])
        y = int(self._joy_state['down']) - int(self._joy_state['up'])
        if x != self._axis['x']:
            self._axis['x'] = x
            self.ui.write(e.EV_ABS, e.ABS_X, x)
            self._log(f"axis X → {x}")
        if y != self._axis['y']:
            self._axis['y'] = y
            self.ui.write(e.EV_ABS, e.ABS_Y, y)
            self._log(f"axis Y → {y}")
        self.ui.syn()

    def _emit_button(self, spec, pressed):
        key_code = getattr(e, spec['evdev_key'])
        self._log(f"button {spec['name']} {'↓' if pressed else '↑'} → {spec['evdev_key']}")
        self.ui.write(e.EV_KEY, key_code, 1 if pressed else 0)
        self.ui.syn()

    # ------------------------------------------------------------------ #

    def cleanup(self):
        # Release every held input so a restart never inherits a stuck state.
        try:
            for spec in self._pins:
                if spec['kind'] == 'button' and self._stable[spec['pin']]:
                    self.ui.write(e.EV_KEY, getattr(e, spec['evdev_key']), 0)
            for chord in self._chords:
                if chord['active']:
                    chord['ui'].write(e.EV_KEY, chord['key_code'], 0)
            self.ui.write(e.EV_ABS, e.ABS_X, 0)
            self.ui.write(e.EV_ABS, e.ABS_Y, 0)
            self.ui.syn()
            if self.ui2 is not None:
                self.ui2.syn()
        except Exception:
            pass
        GPIO.cleanup()
        self.ui.close()
        if self.ui2 is not None:
            self.ui2.close()
        self._log("GPIO cleaned up.")


def main():
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    try:
        config = load_config()
    except FileNotFoundError:
        print(f"ERROR: config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    arcade = ArcadeInput(config, verbose=verbose)
    print("Pi Arcade GPIO daemon running. Send SIGTERM or press Ctrl+C to stop.")

    def shutdown(sig, frame):
        print("\nShutting down...")
        arcade.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    arcade.poll_forever()


if __name__ == '__main__':
    main()
