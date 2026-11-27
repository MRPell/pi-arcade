"""The arcade-profiles.enforce cabinet flag and the pad -> input decoding."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arcade_profiles.flag import enforce_enabled  # noqa: E402
from arcade_profiles.pad import EV_ABS, EV_KEY, PadDecoder, input_codes  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), '..')


class FlagTest(unittest.TestCase):
    def _write(self, text):
        fd, path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w') as f:
            f.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_shipped_cabinet_config_is_off(self):
        self.assertFalse(enforce_enabled(os.path.join(REPO, 'config', 'cabinet.json')))

    def test_dev_cabinet_config_is_on(self):
        self.assertTrue(enforce_enabled(os.path.join(REPO, 'config', 'cabinet.dev.json')))

    def test_on_only_when_true(self):
        self.assertTrue(enforce_enabled(self._write(json.dumps({'arcade-profiles.enforce': True}))))
        self.assertFalse(enforce_enabled(self._write(json.dumps({'arcade-profiles.enforce': 'yes'}))))

    def test_missing_or_broken_config_is_off(self):
        self.assertFalse(enforce_enabled('/nonexistent/cabinet.json'))
        self.assertFalse(enforce_enabled(self._write('{not json')))


class PadDecoderTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, 'config', 'gpio_map.json')) as f:
            gpio_map = json.load(f)
        # Real evdev codes: BTN_SOUTH=304 ... BTN_START=315, ABS_X=0, ABS_Y=1.
        codes = {'BTN_SOUTH': 304, 'BTN_EAST': 305, 'BTN_NORTH': 307, 'BTN_WEST': 308,
                 'BTN_TL': 310, 'BTN_TR': 311, 'BTN_SELECT': 314, 'BTN_START': 315}
        self.d = PadDecoder(input_codes(gpio_map, codes.__getitem__), abs_x=0, abs_y=1)

    def test_buttons_map_to_panel_names(self):
        self.assertEqual(self.d.feed(EV_KEY, 304, 1), [('1', True)])
        self.assertEqual(self.d.feed(EV_KEY, 311, 0), [('6', False)])
        self.assertEqual(self.d.feed(EV_KEY, 314, 1), [('coin', True)])
        self.assertEqual(self.d.feed(EV_KEY, 315, 1), [('start', True)])

    def test_autorepeat_ignored(self):
        self.assertEqual(self.d.feed(EV_KEY, 304, 2), [])

    def test_axes_become_direction_presses(self):
        self.assertEqual(self.d.feed(EV_ABS, 0, -1), [('left', True)])
        self.assertEqual(self.d.feed(EV_ABS, 0, 1), [('left', False), ('right', True)])
        self.assertEqual(self.d.feed(EV_ABS, 0, 0), [('right', False)])
        self.assertEqual(self.d.feed(EV_ABS, 1, -1), [('up', True)])
        self.assertEqual(self.d.feed(EV_ABS, 1, 0), [('up', False)])


if __name__ == '__main__':
    unittest.main()
