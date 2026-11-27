"""Turn Pi Arcade Controller evdev events into panel input names.

Names: up, down, left, right, 1-6, coin, start. Kept free of evdev so it can be
tested anywhere; the caller resolves evdev key names to codes.
"""

# Linux input event types (kernel ABI, linux/input-event-codes.h).
EV_KEY = 0x01
EV_ABS = 0x03

# gpio_map.json button name -> panel input name.
BUTTON_INPUTS = {
    'fire': '1', 'action2': '2', 'action3': '3', 'action4': '4',
    'action5': '5', 'action6': '6', 'coin': 'coin', 'start': 'start',
}


def input_codes(gpio_map, code_for):
    """Map each button's evdev code to its panel input name.

    code_for turns an evdev key name (e.g. 'BTN_SOUTH') into its code.
    """
    return {code_for(cfg['evdev_key']): BUTTON_INPUTS[name]
            for name, cfg in gpio_map['buttons'].items() if name in BUTTON_INPUTS}


class PadDecoder:
    def __init__(self, button_inputs, abs_x, abs_y):
        self._buttons = button_inputs
        self._axes = {abs_x: ('left', 'right'), abs_y: ('up', 'down')}
        self._axis_dir = {}

    def feed(self, ev_type, code, value):
        """Return [(input, pressed)] for one evdev event."""
        if ev_type == EV_KEY and code in self._buttons and value in (0, 1):
            return [(self._buttons[code], value == 1)]
        if ev_type == EV_ABS and code in self._axes:
            neg, pos = self._axes[code]
            new = neg if value < 0 else pos if value > 0 else None
            old = self._axis_dir.get(code)
            if new == old:
                return []
            self._axis_dir[code] = new
            out = []
            if old is not None:
                out.append((old, False))
            if new is not None:
                out.append((new, True))
            return out
        return []
