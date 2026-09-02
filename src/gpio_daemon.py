#!/usr/bin/env python3
"""
Pi Arcade GPIO Daemon

Reads GPIO inputs (joystick + buttons) and publishes them as a virtual
gamepad via Linux uinput. RetroArch/MAME see a standard gamepad device.

Config: ../config/gpio_map.json
Requires: RPi.GPIO, python3-evdev
Run as root (uinput access): sudo python3 gpio_daemon.py
"""

import json
import os
import signal
import sys
import threading
import time

import RPi.GPIO as GPIO
from evdev import UInput, ecodes as e, AbsInfo

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'gpio_map.json')

# Virtual gamepad capabilities exposed to the OS.
# Joystick axes: ABS_X (left/right) and ABS_Y (up/down), range -1..1.
# Buttons: BTN_SOUTH (fire), BTN_EAST (action2), BTN_SELECT (coin), BTN_START (start).
GAMEPAD_CAPS = {
    e.EV_KEY: [
        e.BTN_SOUTH,    # fire / primary action
        e.BTN_EAST,     # secondary action
        e.BTN_SELECT,   # coin insert
        e.BTN_START,    # player 1 start
    ],
    e.EV_ABS: [
        (e.ABS_X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (e.ABS_Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


class ArcadeInput:
    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.debounce_ms = config.get('debounce_ms', 20)
        self._joy_state = {'up': False, 'down': False, 'left': False, 'right': False}
        self._lock = threading.Lock()

        self.ui = UInput(GAMEPAD_CAPS, name='Pi Arcade Controller', version=0x1)
        self._log(f"Virtual gamepad created: {self.ui.device.path}")

        self._setup_gpio()

    def _log(self, msg):
        if self.verbose:
            print(f"[gpio_daemon] {msg}", flush=True)

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)

        joy = self.config['joystick']
        for direction, pin in joy.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.BOTH,
                callback=lambda ch, d=direction: self._on_joy(ch, d),
                bouncetime=self.debounce_ms,
            )
            self._log(f"  joystick {direction:5s} → GPIO {pin}")

        buttons = self.config['buttons']
        for name, cfg in buttons.items():
            pin = cfg['gpio']
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.BOTH,
                callback=lambda ch, c=cfg, n=name: self._on_button(ch, n, c),
                bouncetime=self.debounce_ms,
            )
            self._log(f"  button   {name:12s} → GPIO {pin}")

    # ------------------------------------------------------------------ #
    # Joystick                                                             #
    # ------------------------------------------------------------------ #

    def _on_joy(self, channel, direction):
        pressed = not GPIO.input(channel)  # active-low: LOW = pressed
        self._log(f"joy {direction} {'↓' if pressed else '↑'}")

        with self._lock:
            self._joy_state[direction] = pressed
            x = int(self._joy_state['right']) - int(self._joy_state['left'])
            y = int(self._joy_state['down']) - int(self._joy_state['up'])

        self.ui.write(e.EV_ABS, e.ABS_X, x)
        self.ui.write(e.EV_ABS, e.ABS_Y, y)
        self.ui.syn()

    # ------------------------------------------------------------------ #
    # Buttons                                                              #
    # ------------------------------------------------------------------ #

    def _on_button(self, channel, name, cfg):
        pressed = not GPIO.input(channel)  # active-low

        action = cfg.get('action')
        if action == 'coin_start_sequence':
            if pressed:
                self._log("coin_start triggered")
                threading.Thread(
                    target=self._coin_start_sequence,
                    args=(cfg,),
                    daemon=True,
                ).start()
            # ignore release — the sequence handles its own key-ups
            return

        key_name = cfg.get('evdev_key')
        key_code = getattr(e, key_name)
        value = 1 if pressed else 0
        self._log(f"button {name} {'↓' if pressed else '↑'} → {key_name}")
        self.ui.write(e.EV_KEY, key_code, value)
        self.ui.syn()

    def _coin_start_sequence(self, cfg):
        """Press SELECT (coin insert), release, wait, press START, release."""
        coin_hold  = cfg.get('coin_hold_ms', 100) / 1000.0
        gap        = cfg.get('start_delay_ms', 200) / 1000.0
        start_hold = cfg.get('start_hold_ms', 100) / 1000.0

        self.ui.write(e.EV_KEY, e.BTN_SELECT, 1)
        self.ui.syn()
        time.sleep(coin_hold)
        self.ui.write(e.EV_KEY, e.BTN_SELECT, 0)
        self.ui.syn()

        time.sleep(gap)

        self.ui.write(e.EV_KEY, e.BTN_START, 1)
        self.ui.syn()
        time.sleep(start_hold)
        self.ui.write(e.EV_KEY, e.BTN_START, 0)
        self.ui.syn()

    # ------------------------------------------------------------------ #

    def cleanup(self):
        GPIO.cleanup()
        self.ui.close()
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

    # Main thread just keeps the process alive; GPIO callbacks run on their own threads.
    while True:
        time.sleep(60)


if __name__ == '__main__':
    main()
