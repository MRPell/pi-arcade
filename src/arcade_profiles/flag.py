"""The arcade-profiles.enforce cabinet flag.

Usage: python3 -m arcade_profiles.flag CABINET_JSON
Exits 0 when the flag is on, 1 when off. A missing or unreadable config is
off, so a bad deploy leaves the cabinet playing as it did before profiles.
"""

import json
import sys

FLAG = 'arcade-profiles.enforce'


def enforce_enabled(path):
    try:
        with open(path) as f:
            return json.load(f).get(FLAG) is True
    except (OSError, ValueError, AttributeError):
        return False


if __name__ == '__main__':
    sys.exit(0 if len(sys.argv) == 2 and enforce_enabled(sys.argv[1]) else 1)
