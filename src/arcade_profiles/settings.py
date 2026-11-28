"""The cabinet's settings: the arcade-profiles.enforce flag and the profiles
(combos, hours, time limits).

The owner changes them from their computer (admin/, `make admin`), which
writes them here, into the cabinet's state directory, through this module's
command line. Until it has, the cabinet uses the shipped config/cabinet.json
and config/profiles.json. They live outside the repo copy so `make deploy`
never undoes the owner's changes. Nothing at the cabinet writes them.

    python3 -m arcade_profiles.settings show
        Print {"enforce": bool, "profiles": {...}, "from_admin": bool} as JSON.
    python3 -m arcade_profiles.settings write < CHANGE_JSON
        CHANGE_JSON is {"enforce": bool} and/or {"profiles": {...}}. Profiles
        are checked first; a bad change writes nothing. Prints what `show`
        prints, or {"error": "..."} and exits 1.
"""

import json
import os
import sys

from .flag import FLAG, enforce_enabled
from .profiles import ProfileError, parse_profiles
from .session import state_dir

REPO_DIR = os.environ.get(
    'PI_ARCADE_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
CABINET = 'cabinet.json'
PROFILES = 'profiles.json'


class SettingsError(ValueError):
    pass


def default_cabinet():
    return os.environ.get('PI_ARCADE_CABINET_CONFIG', os.path.join(REPO_DIR, 'config', CABINET))


def _pick(directory, name, default):
    override = os.path.join(directory or state_dir(), name)
    return override if os.path.exists(override) else default


def cabinet_path(directory=None, default=None):
    return _pick(directory, CABINET, default or default_cabinet())


def profiles_path(directory=None):
    return _pick(directory, PROFILES, os.path.join(REPO_DIR, 'config', PROFILES))


def enforce_on(directory=None, default=None):
    return enforce_enabled(cabinet_path(directory, default))


def load_raw_profiles(directory=None):
    with open(profiles_path(directory)) as f:
        return json.load(f)


def load_profiles(directory=None):
    return parse_profiles(load_raw_profiles(directory))


def check_profiles(raw):
    """parse_profiles, with any malformed input reported as a ProfileError."""
    try:
        return parse_profiles(raw)
    except ProfileError:
        raise
    except KeyError as e:
        raise ProfileError('a profile is missing %s' % e)
    except (TypeError, AttributeError, ValueError):
        raise ProfileError('profiles are not in the expected shape')


def show(directory=None, default=None):
    directory = directory or state_dir()
    return {'enforce': enforce_on(directory, default),
            'profiles': load_raw_profiles(directory),
            'from_admin': any(os.path.exists(os.path.join(directory, n)) for n in (CABINET, PROFILES))}


def _write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def write(change, directory=None):
    directory = directory or state_dir()
    if not isinstance(change, dict) or not change or set(change) - {'enforce', 'profiles'}:
        raise SettingsError('a change is {"enforce": true|false} and/or {"profiles": {...}}')
    if 'enforce' in change and not isinstance(change['enforce'], bool):
        raise SettingsError('enforce must be true or false')
    if 'profiles' in change:
        check_profiles(change['profiles'])
    os.makedirs(directory, exist_ok=True)
    if 'profiles' in change:
        _write_json(os.path.join(directory, PROFILES), change['profiles'])
    if 'enforce' in change:
        _write_json(os.path.join(directory, CABINET), {
            '_comment': 'Written by the admin on the owner\'s computer (make admin). '
                        'Read each time EmulationStation quits.',
            FLAG: change['enforce']})


class ProfilesWatch:
    """The profiles, re-read whenever the file changes, so the owner's changes
    reach a screen that is already up. A file that fails to load keeps the
    last good profiles."""

    def __init__(self, directory=None):
        self._directory = directory
        self._raw = None
        self.profiles = None

    def current(self):
        try:
            with open(profiles_path(self._directory)) as f:
                raw = f.read()
        except OSError:
            raw = None
        if raw != self._raw:
            try:
                self.profiles = parse_profiles(json.loads(raw))
                self._raw = raw
            except (TypeError, ValueError, KeyError, AttributeError):
                if self.profiles is None:
                    raise
        return self.profiles


def main(argv):
    if argv == ['show']:
        print(json.dumps(show()))
        return 0
    if argv == ['write']:
        try:
            write(json.loads(sys.stdin.read()))
        except (ValueError, SettingsError) as e:   # ProfileError is a ValueError
            print(json.dumps({'error': str(e)}))
            return 1
        print(json.dumps(show()))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
