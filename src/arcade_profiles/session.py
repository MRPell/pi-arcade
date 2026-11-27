"""Who is signed in at the cabinet, kept in STATE_DIR/session.json so later
steps (game launches, high scores) can read it."""

import json
import os
import time

DEFAULT_STATE_DIR = '/home/pi/.pi-arcade'


def state_dir():
    return os.environ.get('PI_ARCADE_STATE_DIR', DEFAULT_STATE_DIR)


def _path(directory):
    return os.path.join(directory, 'session.json')


def write_session(directory, profile, wall_time=None):
    os.makedirs(directory, exist_ok=True)
    record = {
        'profile': profile.id,
        'name': profile.name,
        'role': profile.role,
        'signed_in_at': int(time.time() if wall_time is None else wall_time),
    }
    tmp = _path(directory) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(record, f)
    os.replace(tmp, _path(directory))
    return record


def read_session(directory):
    try:
        with open(_path(directory)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clear_session(directory):
    try:
        os.remove(_path(directory))
    except FileNotFoundError:
        pass
