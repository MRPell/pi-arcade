"""A stand-in for the cabinet's boot flow, for walking arcade profiles without
the Pi: the real sign-in logic (arcade_profiles.signin) in front of a
simplified EmulationStation and game.

It follows scripts/arcade-session.sh: flag off, boot straight to
EmulationStation and quitting it drops to the console, as before profiles;
flag on, sign-in first and quitting EmulationStation returns to sign-in.
"""

import time

from arcade_profiles.session import clear_session, read_session, write_session
from arcade_profiles.signin import SignIn

GAMES = ['Galaga', 'Pac-Man', 'Donkey Kong', 'Frogger', 'Super Mario Bros.']
ES_MENU = ['Quit EmulationStation', 'Close menu']
GAME_LOG = 8


class CabinetSim:
    def __init__(self, profiles, enforce, state_dir, clock=time.monotonic):
        self.profiles = profiles
        self.enforce = enforce
        self.state_dir = state_dir
        self.clock = clock
        self.boot()

    def boot(self):
        clear_session(self.state_dir)
        self.cursor = 0
        self.menu_cursor = 0
        self.game = None
        self.game_log = []
        self.held = set()
        if self.enforce:
            self._start_signin()
        else:
            self.view = 'menu'

    def _start_signin(self):
        clear_session(self.state_dir)
        self.signin = SignIn(self.profiles, self.clock())
        self.view = 'signin'

    def feed(self, name, pressed):
        if pressed:
            self.held.add(name)
        else:
            self.held.discard(name)
        handler = getattr(self, '_on_' + self.view)
        handler(name, pressed)

    def tick(self):
        if self.view in ('signin', 'welcome'):
            self.signin.tick(self.clock())

    # -- sign-in (the real logic) ---------------------------------------- #

    def _on_signin(self, name, pressed):
        self.signin.feed(name, pressed, self.clock())
        if self.signin.signed_in is not None:
            write_session(self.state_dir, self.signin.signed_in)
            self.view = 'welcome'

    def _on_welcome(self, name, pressed):
        self.signin.feed(name, pressed, self.clock())
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
            self.game = GAMES[self.cursor]
            self.game_log = []
            self.view = 'game'
        elif name == 'start':
            self.menu_cursor = 0
            self.view = 'esmenu'

    def _on_esmenu(self, name, pressed):
        if not pressed:
            return
        if name in ('up', 'down'):
            step = -1 if name == 'up' else 1
            self.menu_cursor = (self.menu_cursor + step) % len(ES_MENU)
        elif name == '2' or (name == '1' and ES_MENU[self.menu_cursor] == 'Close menu'):
            self.view = 'menu'
        elif name == '1':
            if self.enforce:
                self._start_signin()
            else:
                self.view = 'shell'

    def _on_game(self, name, pressed):
        if {'coin', 'start'} <= self.held:
            self.game = None
            self.view = 'menu'
            return
        if pressed:
            self.game_log = (self.game_log + [name])[-GAME_LOG:]

    def _on_shell(self, name, pressed):
        pass

    # -------------------------------------------------------------------- #

    def state(self):
        self.tick()
        state = {
            'view': self.view,
            'enforce': self.enforce,
            'session': read_session(self.state_dir),
        }
        if self.view in ('signin', 'welcome'):
            state['screen'] = self.signin.screen()
        elif self.view == 'menu':
            state['menu'] = {'games': GAMES, 'cursor': self.cursor}
        elif self.view == 'esmenu':
            state['esmenu'] = {'items': ES_MENU, 'cursor': self.menu_cursor}
        elif self.view == 'game':
            state['game'] = {'title': self.game, 'log': self.game_log}
        return state
