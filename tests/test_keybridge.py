"""Tests for the gamepad -> keyboard translation used by ports.

Run on the Pi (needs python3-evdev for the key code table):
    python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from evdev import ecodes as e  # noqa: E402

from keybridge import Translator  # noqa: E402

KEYMAP = {
    'buttons': {'BTN_SOUTH': 'KEY_SPACE', 'BTN_START': 'KEY_ENTER'},
    'axes': {'left': 'KEY_LEFT', 'right': 'KEY_RIGHT', 'up': 'KEY_UP', 'down': 'KEY_DOWN'},
    'exit_chord': ['BTN_SELECT', 'BTN_START'],
}


class TranslatorTest(unittest.TestCase):
    def setUp(self):
        self.t = Translator(KEYMAP)

    def test_mapped_button_press_and_release(self):
        self.assertEqual(self.t.feed(e.EV_KEY, e.BTN_SOUTH, 1), [(e.KEY_SPACE, 1)])
        self.assertEqual(self.t.feed(e.EV_KEY, e.BTN_SOUTH, 0), [(e.KEY_SPACE, 0)])

    def test_unmapped_button_emits_nothing(self):
        self.assertEqual(self.t.feed(e.EV_KEY, e.BTN_EAST, 1), [])

    def test_axis_left_then_centre(self):
        self.assertEqual(self.t.feed(e.EV_ABS, e.ABS_X, -1), [(e.KEY_LEFT, 1)])
        self.assertEqual(self.t.feed(e.EV_ABS, e.ABS_X, 0), [(e.KEY_LEFT, 0)])

    def test_axis_flip_releases_old_direction_first(self):
        self.t.feed(e.EV_ABS, e.ABS_X, -1)
        self.assertEqual(self.t.feed(e.EV_ABS, e.ABS_X, 1), [(e.KEY_LEFT, 0), (e.KEY_RIGHT, 1)])

    def test_vertical_axis(self):
        self.assertEqual(self.t.feed(e.EV_ABS, e.ABS_Y, -1), [(e.KEY_UP, 1)])
        self.assertEqual(self.t.feed(e.EV_ABS, e.ABS_Y, 1), [(e.KEY_UP, 0), (e.KEY_DOWN, 1)])

    def test_exit_chord(self):
        self.t.feed(e.EV_KEY, e.BTN_SELECT, 1)
        self.assertFalse(self.t.exit_requested)
        self.t.feed(e.EV_KEY, e.BTN_START, 1)
        self.assertTrue(self.t.exit_requested)

    def test_exit_chord_needs_both_held(self):
        self.t.feed(e.EV_KEY, e.BTN_SELECT, 1)
        self.t.feed(e.EV_KEY, e.BTN_SELECT, 0)
        self.t.feed(e.EV_KEY, e.BTN_START, 1)
        self.assertFalse(self.t.exit_requested)

    def test_output_keys_lists_every_key_the_map_can_emit(self):
        self.assertEqual(
            set(self.t.output_keys()),
            {e.KEY_SPACE, e.KEY_ENTER, e.KEY_LEFT, e.KEY_RIGHT, e.KEY_UP, e.KEY_DOWN},
        )


if __name__ == '__main__':
    unittest.main()
