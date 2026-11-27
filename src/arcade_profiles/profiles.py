"""Load and check config/profiles.json."""

import json
from collections import namedtuple

from .rules import LimitsError, parse_limits

# limits is None for the owner, who plays without limits.
Profile = namedtuple('Profile', 'id name role combo limits')

DIRECTIONS = ('up', 'down', 'left', 'right')
BUTTONS = ('1', '2', '3', '4', '5', '6')
# Inputs a combo may use. Coin is left out on purpose: Coin + any button is a
# RetroArch hotkey and Coin + Start exits a game, and on the sign-in screen
# Coin clears a half-entered combo.
COMBO_INPUTS = DIRECTIONS + BUTTONS + ('start',)
ROLES = ('owner', 'player', 'guest')
MAX_COMBO = 8


class ProfileError(ValueError):
    pass


def load_profiles(path):
    with open(path) as f:
        return parse_profiles(json.load(f))


def parse_profiles(data):
    profiles = []
    for raw in data.get('profiles', []):
        combo = tuple(raw.get('combo', []))
        role = raw['role']
        if role not in ROLES:
            raise ProfileError('%s: role must be one of %s' % (raw['id'], ', '.join(ROLES)))
        if role == 'owner':
            if 'limits' in raw:
                raise ProfileError('%s: the owner has no limits' % raw['id'])
            limits = None
        else:
            try:
                limits = parse_limits(raw['id'], raw.get('limits'))
            except LimitsError as e:
                raise ProfileError(str(e))
        p = Profile(raw['id'], raw['name'], role, combo, limits)
        if not combo or len(combo) > MAX_COMBO:
            raise ProfileError('%s: combo needs 1 to %d inputs' % (p.id, MAX_COMBO))
        for name in combo:
            if name == 'coin':
                raise ProfileError('%s: coin cannot be part of a combo' % p.id)
            if name not in COMBO_INPUTS:
                raise ProfileError('%s: unknown input %r' % (p.id, name))
        profiles.append(p)

    for role in ('owner', 'guest'):
        if sum(1 for p in profiles if p.role == role) != 1:
            raise ProfileError('there must be exactly one %s profile' % role)
    for field in ('id', 'name'):
        values = [getattr(p, field) for p in profiles]
        if len(set(values)) != len(values):
            raise ProfileError('profile %ss must be unique' % field)

    # Combos are matched as soon as they are complete, so none may be the
    # start of another (or the longer one could never be entered).
    for a in profiles:
        for b in profiles:
            if a is not b and b.combo[:len(a.combo)] == a.combo:
                raise ProfileError("%s's combo starts with %s's combo" % (b.id, a.id))
    return profiles
