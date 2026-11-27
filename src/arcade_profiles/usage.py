"""The play ledger: how long each profile has played, kept in
STATE_DIR/usage.json so it survives reboots.

    {"since": 1764260000,
     "plays": [{"profile": "theo", "start": 1764270000, "seconds": 1800.0}],
     "open":  {"profile": "theo", "start": ..., "start_mono": ..., "limit": 2400.0,
               "seconds": 120.0, "boot": "...", "ended": null, "guard": 1234}}

A play counts from game start to game end, measured on the monotonic clock
so a clock change mid-game neither adds nor removes time. `open` is the game
running now; its seconds are written as it goes, so a power cut loses at most
one heartbeat, and a stale open play from an earlier boot is closed with what
it had.
"""

import contextlib
import fcntl
import json
import os
import time

FILE = 'usage.json'
LOCK = 'usage.lock'


def boot_id():
    try:
        with open('/proc/sys/kernel/random/boot_id') as f:
            return f.read().strip()
    except OSError:
        return None


@contextlib.contextmanager
def locked(directory):
    """The ledger, held exclusively, for processes that share it (the game
    start and end hooks and the guard that stops a game at its limit)."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, LOCK), 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield Ledger(directory)


class Ledger:
    def __init__(self, directory, wall_time=None):
        self.path = os.path.join(directory, FILE)
        os.makedirs(directory, exist_ok=True)
        try:
            with open(self.path) as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {'since': int(time.time() if wall_time is None else wall_time),
                         'plays': [], 'open': None}
            self.save()

    @property
    def since(self):
        return self.data['since']

    @property
    def open(self):
        return self.data['open']

    def save(self):
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    def plays(self):
        """Every play, the running one included with its time so far."""
        out = list(self.data['plays'])
        if self.data['open']:
            o = self.data['open']
            out.append({'profile': o['profile'], 'start': o['start'], 'seconds': o['seconds']})
        return out

    def latest_start(self):
        starts = [p['start'] for p in self.plays()]
        return max(starts) if starts else None

    def recover(self, boot):
        """Close a play left open by a power cut or crash in an earlier boot."""
        o = self.data['open']
        if o and o.get('boot') != boot:
            self._close()

    def start(self, profile_id, wall, mono, limit=None, boot=None, **extra):
        if self.data['open']:
            self._close()
        self.data['open'] = dict({'profile': profile_id, 'start': wall, 'start_mono': mono,
                                  'limit': limit, 'seconds': 0.0, 'boot': boot, 'ended': None},
                                 **extra)
        self.save()

    def elapsed(self, mono):
        o = self.data['open']
        seconds = max(0.0, mono - o['start_mono'])
        return seconds if o['limit'] is None else min(seconds, o['limit'])

    def heartbeat(self, mono):
        """Record the running game's time so far; True once it reaches its limit."""
        o = self.data['open']
        if not o:
            return False
        o['seconds'] = self.elapsed(mono)
        self.save()
        return o['limit'] is not None and mono - o['start_mono'] >= o['limit']

    def mark_ended(self, why):
        self.data['open']['ended'] = why
        self.save()

    def finish(self, mono):
        """End the running game; returns its open record (None if none)."""
        o = self.data['open']
        if not o:
            return None
        o['seconds'] = self.elapsed(mono)
        self._close()
        return o

    def _close(self):
        o = self.data['open']
        self.data['plays'].append({'profile': o['profile'], 'start': o['start'],
                                   'seconds': round(o['seconds'], 1)})
        self.data['open'] = None
        self.save()
