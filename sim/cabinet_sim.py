"""A stand-in for the cabinet's boot flow, for walking arcade profiles without
the Pi: the real sign-in logic (arcade_profiles.signin) and the real play
rules (arcade_profiles.play) in front of a simplified EmulationStation and game.

It follows scripts/arcade-session.sh and the runcommand hooks: flag off, boot
straight to EmulationStation, games start with no checks, and quitting it
drops to the console, as before profiles. Flag on, sign-in first; starting a
game is checked against the signed-in profile's hours and time left, a game
is stopped when its time runs out, and quitting EmulationStation returns to
sign-in.

The flag and the profiles are read from the cabinet's settings in state_dir
(arcade_profiles.settings), which the admin on the owner's computer writes
(make admin-sim): the flag each time EmulationStation quits, the profiles on
every screen, as on the cabinet.

The stand-in games score points (Button 1: 100, Button 2: 1,000) and, like
mame2003-plus, save a new top score to their hiscore file in state_dir/hi
when they exit; the real high-score code (arcade_profiles.scores) reads it
from there. An idle sign-in screen rotates through the high scores.
"""

import datetime as dt
import os
import time
import uuid

from arcade_profiles import play, scores
from arcade_profiles.session import clear_session, read_session, write_session
from arcade_profiles.settings import ProfilesWatch, enforce_on
from arcade_profiles.signin import SignIn
from arcade_profiles.usage import Ledger

# Title and the rom whose hiscore save it writes (config/hiscores.json); None keeps no score.
GAMES = [('Galaga', 'galaga'), ('Pac-Man', 'pacman'), ('Donkey Kong', 'dkong'),
         ('Space Invaders', 'invaders'), ('Super Mario Bros.', None)]
POINTS = {'1': 100, '2': 1000}
ES_MENU = ['Quit EmulationStation', 'Close menu']
GAME_LOG = 8
# A button pressed in the game as it is stopped must not also dismiss the screen.
DISMISS_GRACE = 1.5


class SimClock:
    """The simulated cabinet's clocks. Time runs at real speed; advance() moves
    both clocks on (time passing), set_wall() only the wall clock (the clock
    being set or wrong). synced is whether network time has set the clock."""

    def __init__(self, wall=None, mono_source=time.monotonic):
        self._source = mono_source
        self._extra = 0.0
        self._wall_at_zero = (time.time() if wall is None else wall) - self.mono()
        self.synced = True

    def mono(self):
        return self._source() + self._extra

    def wall(self):
        return self._wall_at_zero + self.mono()

    def advance(self, seconds):
        self._extra += seconds

    def set_wall(self, wall):
        self._wall_at_zero = wall - self.mono()


class CabinetSim:
    def __init__(self, state_dir, clock=None):
        self.state_dir = state_dir
        self.clock = clock or SimClock()
        self.boot_id = uuid.uuid4().hex
        self._watch = ProfilesWatch(state_dir)
        self.hi_dir = os.path.join(state_dir, 'hi')
        self.games = scores.load_games()
        self.ledger = None
        self.boot()

    @property
    def profiles(self):
        return self._watch.current()

    def enforce_setting(self):
        """arcade-profiles.enforce as the settings say now."""
        return enforce_on(self.state_dir)

    def boot(self):
        clear_session(self.state_dir)
        self.cursor = 0
        self.menu_cursor = 0
        self.game = None
        self.game_log = []
        self.game_score = 0
        self.held = set()
        self.notice = None
        if self.enforce_setting():
            self._start_signin()
        else:
            self.enforced = False      # this EmulationStation is under profiles
            self.view = 'menu'

    def _quit_emulationstation(self):
        """What arcade-session.sh does when EmulationStation quits: the flag is read again."""
        if self.enforce_setting():
            self._start_signin()
        else:
            self.enforced = False      # turned off: to the console, as before profiles
            self.view = 'shell'

    def _profile(self):
        session = read_session(self.state_dir)
        return next((p for p in self.profiles if session and p.id == session['profile']), None)

    def _check(self, profile):
        return play.check(self.profiles, profile, self.clock.wall(), self.ledger, self.clock.synced)

    def _start_signin(self):
        if self.ledger is None:
            self.ledger = Ledger(self.state_dir, self.clock.wall())
            self.ledger.recover(self.boot_id)
        self.enforced = True
        clear_session(self.state_dir)
        wall = self.clock.wall

        def describe(profile):
            return play.status_lines(self.profiles, self._check(profile), wall())
        self.signin = SignIn(self.profiles, self.clock.mono(), describe)
        self.attract = scores.Attract(self.clock.mono())
        self.view = 'signin'

    def feed(self, name, pressed):
        if pressed:
            self.held.add(name)
        else:
            self.held.discard(name)
        self.tick()
        if self.view == 'scores':
            if pressed and self.attract.input(self.clock.mono()):
                self.view = 'signin'         # woke from the high scores; the press does nothing else
            return
        if self.view == 'signin' and pressed:
            self.attract.input(self.clock.mono())
        handler = getattr(self, '_on_' + self.view)
        handler(name, pressed)

    def tick(self):
        mono = self.clock.mono()
        if self.view in ('signin', 'welcome', 'scores'):
            self.signin.update_profiles(self.profiles, mono)
            if self.view == 'welcome' and self.signin.signed_in is None:
                clear_session(self.state_dir)      # the owner removed this profile
                self.view = 'signin'
            self.signin.tick(mono)
            if self.view != 'welcome':
                idle = scores.signin_idle(self.signin.screen()) and bool(self._score_rows())
                self.view = 'scores' if self.attract.tick(mono, idle) else 'signin'
        elif self.view == 'game' and self.enforced:
            play.refresh_limit(self.profiles, self.ledger, self.clock.wall(), mono)
            if self.ledger.heartbeat(mono):
                self.ledger.mark_ended('time')
                self._end_game()
        elif self.view in ('refused', 'timeup') and mono >= self.notice['until']:
            self.view = 'menu'

    # -- sign-in (the real logic) ---------------------------------------- #

    def _on_signin(self, name, pressed):
        self.signin.feed(name, pressed, self.clock.mono())
        if self.signin.signed_in is not None:
            write_session(self.state_dir, self.signin.signed_in, self.clock.wall())
            self.view = 'welcome'

    def _on_welcome(self, name, pressed):
        self.signin.feed(name, pressed, self.clock.mono())
        if self.signin.done:
            self.view = 'menu'

    # -- EmulationStation stand-in --------------------------------------- #

    def _on_menu(self, name, pressed):
        if not pressed:
            return
        if name in ('up', 'down'):
            step = -1 if name == 'up' else 1
            self.cursor = (self.cursor + step) % len(GAMES)
        elif name == '1':
            self._launch(*GAMES[self.cursor])
        elif name == 'start':
            self.menu_cursor = 0
            self.view = 'esmenu'

    def _score_rows(self):
        return scores.rows(self.state_dir, self.profiles, self.games)

    def _sync_scores(self, holder):
        scores.sync(self.state_dir, holder, self.clock.wall(), self.games, self.hi_dir)

    def _launch(self, title, rom):
        """What runcommand-onstart.sh does on the cabinet, then the game."""
        if self.enforced:
            self._sync_scores(None)
            profile = self._profile()
            if profile is None:
                self._notice(play.not_signed_in_screen(read_session(self.state_dir)))
                return
            wall = self.clock.wall()
            self.ledger.recover(self.boot_id)
            decision = self._check(profile)
            if not decision.allowed:
                self._notice(play.refusal_screen(self.profiles, decision, wall))
                return
            self.ledger.start(profile.id, wall, self.clock.mono(),
                              play.play_seconds(decision, wall), self.boot_id)
        self.game = title
        self.game_rom = rom
        self.game_log = []
        self.game_score = 0
        self.view = 'game'

    def _save_hiscore(self):
        """The game exiting: like mame2003-plus, it saves a new top score."""
        game = self.games.get(self.game_rom)
        if game is None or not self.game_score:
            return
        path = os.path.join(self.hi_dir, game.file)
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            data = b''
        if self.game_score > (scores.decode(game, data) or 0):
            os.makedirs(self.hi_dir, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(scores.encode(game, self.game_score, data))

    def _end_game(self):
        """The game exits, then what runcommand-onend.sh does on the cabinet."""
        self._save_hiscore()
        self.game = None
        self.view = 'menu'
        if not self.enforced:
            return
        ended = self.ledger.finish(self.clock.mono())
        profile = ended and next((p for p in self.profiles if p.id == ended['profile']), None)
        self._sync_scores(profile.id if profile else None)
        if ended and ended['ended'] == 'time' and profile is None:
            self._notice(play.removed_screen(read_session(self.state_dir)))
        elif profile is not None and ended['ended'] == 'time':
            self._notice(play.timeup_screen(self.profiles, profile, self.ledger,
                                            self.clock.wall(), self.clock.synced))

    def _notice(self, screen):
        now = self.clock.mono()
        self.notice = dict(screen, shown=now, until=now + play.DISMISS_SECONDS)
        self.view = screen['view']

    def _on_refused(self, name, pressed):
        if pressed and self.clock.mono() - self.notice['shown'] >= DISMISS_GRACE:
            self.view = 'menu'

    _on_timeup = _on_refused

    def _on_esmenu(self, name, pressed):
        if not pressed:
            return
        if name in ('up', 'down'):
            step = -1 if name == 'up' else 1
            self.menu_cursor = (self.menu_cursor + step) % len(ES_MENU)
        elif name == '2' or (name == '1' and ES_MENU[self.menu_cursor] == 'Close menu'):
            self.view = 'menu'
        elif name == '1':
            self._quit_emulationstation()

    def _on_game(self, name, pressed):
        if {'coin', 'start'} <= self.held:
            self._end_game()
            return
        if pressed:
            self.game_log = (self.game_log + [name])[-GAME_LOG:]
            self.game_score += POINTS.get(name, 0) if self.game_rom else 0

    def _on_shell(self, name, pressed):
        pass

    # -------------------------------------------------------------------- #

    def state(self):
        self.tick()
        wall = self.clock.wall()
        now = dt.datetime.fromtimestamp(wall)
        state = {
            'view': self.view,
            'enforce': self.enforce_setting(),
            'enforced': self.enforced,
            'session': read_session(self.state_dir),
            'clock': {'wall': now.strftime('%Y-%m-%dT%H:%M'),
                      'text': '%s, %s' % (now.strftime('%a %d %b %Y'), play.clock_time(now)),
                      'synced': self.clock.synced},
            'usage': play.usage_summary(self.profiles, self.ledger, wall) if self.ledger else None,
            'scores': self._score_rows(),
        }
        if self.view in ('signin', 'welcome'):
            state['screen'] = self.signin.screen()
        elif self.view == 'scores':
            state['screen'] = self.attract.screen(self.clock.mono(), self._score_rows())
        elif self.view in ('refused', 'timeup'):
            state['screen'] = {k: self.notice[k] for k in ('view', 'title', 'lines')}
        elif self.view == 'menu':
            state['menu'] = {'games': [title for title, _ in GAMES], 'cursor': self.cursor}
        elif self.view == 'esmenu':
            state['esmenu'] = {'items': ES_MENU, 'cursor': self.menu_cursor}
        elif self.view == 'game':
            state['game'] = {'title': self.game, 'log': self.game_log,
                             'score': self.game_score if self.game_rom else None}
        return state
