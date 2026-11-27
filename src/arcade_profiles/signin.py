"""The sign-in screen's logic: read a combo, sign a profile in, say who.

Pure state machine fed with panel inputs and a monotonic clock; the console
program (on the cabinet) and the simulator both draw what screen() returns.

An input counts when it is released, and only if it was pressed while this
screen was up and Coin was not held at any point during it. That keeps the
Coin + Start exit chord, and anything still held from leaving
EmulationStation, from ever counting as part of a combo.
"""

ROLE_LABELS = {'owner': 'Owner', 'player': 'Player', 'guest': 'Guest'}


class SignIn:
    ENTRY_TIMEOUT = 5.0     # seconds of no input before a half-entered combo is dropped
    MESSAGE_SECONDS = 3.0   # how long "not recognised" stays up

    def __init__(self, profiles, now, describe=None):
        # describe(profile) -> extra welcome lines (time left, or why play is
        # refused), worked out once at sign-in.
        self._describe = describe or (lambda profile: [])
        self._status = []
        self._profiles = list(profiles)
        self._entry = []
        self._held = set()
        self._void = set()          # held inputs that overlapped Coin
        self._coin_chorded = False  # something else was pressed during this Coin hold
        self._last_input = now
        self._message = None
        self._message_until = 0.0
        self.signed_in = None
        self.done = False

    def update_profiles(self, profiles):
        """The owner changed the profiles from their computer: match against
        the new combos from now on. A half-entered combo starts again."""
        profiles = list(profiles)
        if profiles == self._profiles:
            return
        self._profiles = profiles
        if self.signed_in is None:
            self._entry = []

    def feed(self, name, pressed, now):
        self.tick(now)
        if pressed:
            self._press(name, now)
        elif name in self._held:
            self._release(name, now)

    def tick(self, now):
        if self._entry and now - self._last_input > self.ENTRY_TIMEOUT:
            self._entry = []
        if self._message and now >= self._message_until:
            self._message = None

    def _press(self, name, now):
        self._held.add(name)
        self._last_input = now
        if name == 'coin':
            self._coin_chorded = False
            self._void |= self._held - {'coin'}
            if len(self._held) > 1:
                self._coin_chorded = True
        elif 'coin' in self._held:
            self._void.add(name)
            self._coin_chorded = True

    def _release(self, name, now):
        self._held.discard(name)
        if name == 'coin':
            if not self._coin_chorded and self.signed_in is None:
                self._entry = []
            return
        if name in self._void:
            self._void.discard(name)
            return
        if self.signed_in is not None:
            self.done = True
            return
        self._entry.append(name)
        self._match(now)

    def _match(self, now):
        entry = tuple(self._entry)
        for p in self._profiles:
            if p.combo == entry:
                self.signed_in = p
                self._status = list(self._describe(p))
                self._entry = []
                self._message = None
                return
        if not any(p.combo[:len(entry)] == entry for p in self._profiles):
            self._entry = []
            self._message = 'Combo not recognised. Try again.'
            self._message_until = now + self.MESSAGE_SECONDS

    def screen(self):
        if self.signed_in is not None:
            p = self.signed_in
            return {
                'view': 'welcome',
                'title': 'Signed in: %s' % p.name,
                'lines': ['%s profile' % ROLE_LABELS[p.role]] + self._status
                         + ['', 'Press any button to play'],
                'entered': 0,
                'message': None,
            }
        guest = next(p for p in self._profiles if p.role == 'guest')
        guest_hint = ('Visitors: press Start to play as Guest' if guest.combo == ('start',)
                      else 'Visitors: enter the Guest combo')
        return {
            'view': 'signin',
            'title': 'Who is playing?',
            'lines': [
                'Enter your button combo',
                ' / '.join(p.name for p in self._profiles if p.role != 'guest'),
                '',
                guest_hint,
                'Coin: start the combo again',
            ],
            'entered': len(self._entry),
            'message': self._message,
        }
