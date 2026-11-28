"""High scores and who holds them (arcade-profiles M-4).

The games keep their own high scores: the MAME core saves each game's table in
its hi folder when the game exits. config/hiscores.json says where in those
saves each game's top score is. The cabinet notes who holds each top score in
STATE_DIR/scores.json:

    {"games": {"pacman": {"score": 12340, "holder": "theo", "set_at": 1764270000}}}

Before a game (runcommand-onstart.sh) the top scores are read and any change
since the last read is noted with no holder: it was set while profiles were
off. After a game (runcommand-onend.sh) a changed top score is credited to the
profile that just played. The owner changes a holder from their computer
(arcade_profiles.settings); nothing at the cabinet can.

An idle sign-in screen rotates through the top scores (Attract).
"""

import contextlib
import fcntl
import json
import os
from collections import namedtuple


REPO_DIR = os.environ.get(
    'PI_ARCADE_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
FILE = 'scores.json'
LOCK = 'scores.lock'
# RetroArch on the cabinet sets no savefile_directory, so each MAME core saves
# beside the roms: lr-mame2003 is the cabinet's default core, and the
# runcommand menu can switch a game to lr-mame2003-plus.
DEFAULT_HI_DIRS = ('/home/pi/RetroPie/roms/mame-libretro/mame2003/hi',
                   '/home/pi/RetroPie/roms/mame-libretro/mame2003-plus/hi')
ENCODINGS = ('bcd-le', 'tiles-le')
TILE_BLANK = 0x24

Game = namedtuple('Game', 'rom title file offset length encoding')


class ScoreError(ValueError):
    pass


def hi_dirs():
    """Where the games' hiscore saves are: PI_ARCADE_HISCORE_DIR (folders
    separated by os.pathsep) or the cabinet's MAME cores' hi folders."""
    env = os.environ.get('PI_ARCADE_HISCORE_DIR')
    return env.split(os.pathsep) if env else list(DEFAULT_HI_DIRS)


def load_games(path=None):
    """{rom: Game} from config/hiscores.json."""
    with open(path or os.path.join(REPO_DIR, 'config', 'hiscores.json')) as f:
        raw = json.load(f)['games']
    games = {}
    for rom, g in raw.items():
        if g['encoding'] not in ENCODINGS:
            raise ScoreError('%s: encoding must be one of %s' % (rom, ', '.join(ENCODINGS)))
        games[rom] = Game(rom, g['title'], g['file'], int(g['offset']), int(g['length']), g['encoding'])
    return games


def decode(game, data):
    """The top score in a game's hiscore save, or None if it can't be read."""
    raw = data[game.offset:game.offset + game.length]
    if len(raw) != game.length:
        return None
    digits = []                       # lowest first
    for byte in raw:
        if game.encoding == 'bcd-le':
            lo, hi = byte & 0x0F, byte >> 4
            if lo > 9 or hi > 9:
                return None
            digits += [lo, hi]
        else:
            if byte == TILE_BLANK:
                byte = 0
            if byte > 9:
                return None
            digits.append(byte)
    return sum(d * 10 ** i for i, d in enumerate(digits))


def max_score(game):
    """The highest score the game's save can hold."""
    return 10 ** (game.length * (2 if game.encoding == 'bcd-le' else 1)) - 1


def encode(game, score, data=b''):
    """data (a hiscore save, padded as needed) with its top score set to score:
    what the game writes. Used by the simulator's stand-in games."""
    digits = [int(c) for c in reversed(str(int(score)))]
    per_byte = 2 if game.encoding == 'bcd-le' else 1
    if len(digits) > game.length * per_byte:
        raise ScoreError('%s cannot hold a score of %d' % (game.title, score))
    digits += [0] * (game.length * per_byte - len(digits))
    if per_byte == 2:
        raw = bytes(digits[i] | digits[i + 1] << 4 for i in range(0, len(digits), 2))
    else:
        raw = bytes(digits)
    data = bytes(data).ljust(game.offset + game.length, b'\0')
    return data[:game.offset] + raw + data[game.offset + game.length:]


def save_path(game, directory=None):
    """The game's hiscore save: in directory, or else the one written last
    in hi_dirs() (the core the game last ran on). None if there is none."""
    paths = [os.path.join(d, game.file) for d in ([directory] if directory else hi_dirs())]
    found = [p for p in paths if os.path.isfile(p)]
    return max(found, key=os.path.getmtime) if found else None


def read_top(game, directory=None):
    path = save_path(game, directory)
    if path is None:
        return None
    try:
        with open(path, 'rb') as f:
            return decode(game, f.read())
    except OSError:
        return None


# -- the board: who holds each top score ------------------------------------ #

def _path(directory):
    return os.path.join(directory, FILE)


def read_board(directory):
    try:
        with open(_path(directory)) as f:
            board = json.load(f)
        return board if isinstance(board.get('games'), dict) else {'games': {}}
    except (OSError, ValueError, AttributeError):
        return {'games': {}}


def _write_board(directory, board):
    tmp = _path(directory) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(board, f, indent=2)
        f.write('\n')
    os.replace(tmp, _path(directory))


@contextlib.contextmanager
def locked(directory):
    """The board, held exclusively against the game hooks and the admin; saved on the way out."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, LOCK), 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        board = read_board(directory)
        before = json.dumps(board, sort_keys=True)
        yield board
        if json.dumps(board, sort_keys=True) != before:
            _write_board(directory, board)


def sync(directory, holder, wall, games=None, hiscores=None):
    """Read every game's top score; note each one that changed as held by
    holder (a profile id, or None). Returns the roms that changed."""
    games = load_games() if games is None else games
    changed = []
    with locked(directory) as board:
        for rom, game in games.items():
            top = read_top(game, hiscores)
            if top is None:
                continue
            entry = board['games'].get(rom)
            if entry is not None and entry['score'] == top:
                continue
            board['games'][rom] = {'score': top, 'holder': holder, 'set_at': int(wall)}
            changed.append(rom)
    return changed


def assign(directory, changes, profiles):
    """The owner's changes {rom: profile id or None}, all or nothing."""
    if not isinstance(changes, dict) or not changes:
        raise ScoreError('a score change is {"<game>": "<profile id>" or null}')
    ids = {p.id for p in profiles}
    with locked(directory) as board:
        for rom, holder in changes.items():
            if rom not in board['games']:
                raise ScoreError('there is no high score for %s on the cabinet' % rom)
            if holder is not None and holder not in ids:
                raise ScoreError('%r is not a profile' % (holder,))
        for rom, holder in changes.items():
            board['games'][rom]['holder'] = holder


def rows(directory, profiles, games=None):
    """Every game with a top score above 0, by title, with its holder's name
    (None: no profile holds it)."""
    games = load_games() if games is None else games
    names = {p.id: p.name for p in profiles}
    out = []
    for rom, entry in read_board(directory)['games'].items():
        if rom not in games or not entry.get('score'):
            continue
        holder = entry.get('holder')
        out.append({'game': rom, 'title': games[rom].title, 'score': entry['score'],
                    'holder': holder if holder in names else None,
                    'holder_name': names.get(holder)})
    return sorted(out, key=lambda r: r['title'])


def score_text(score):
    return '{:,}'.format(score)


# -- the idle screen ------------------------------------------------------- #

class Attract:
    """An idle sign-in screen turns into the high-score rotation, one game a
    card. Any input brings sign-in back, and that input does nothing else."""

    IDLE_SECONDS = 30.0
    CARD_SECONDS = 5.0

    def __init__(self, now):
        self._last_input = now
        self._since = None

    @property
    def active(self):
        return self._since is not None

    def input(self, now):
        """An input at the cabinet. True if it woke the screen (so it is not passed on)."""
        woke = self.active
        self._since = None
        self._last_input = now
        return woke

    def tick(self, now, can_show):
        """can_show: sign-in is idle (nothing entered, nobody signed in) and there are scores."""
        if not can_show:
            self._since = None
        elif self._since is None and now - self._last_input >= self.IDLE_SECONDS:
            self._since = now
        return self.active

    def screen(self, now, score_rows):
        index = int((now - self._since) // self.CARD_SECONDS) % len(score_rows)
        row = score_rows[index]
        return {
            'view': 'scores',
            'title': 'High scores',
            'lines': [row['title'], score_text(row['score']),
                      'Held by %s' % (row['holder_name'] or 'no profile'), '',
                      '%d of %d' % (index + 1, len(score_rows)),
                      'Press any button to sign in'],
            'entered': 0,
            'message': None,
            'card': dict(row),
        }


def signin_idle(screen):
    return screen['view'] == 'signin' and not screen['entered'] and not screen['message']
