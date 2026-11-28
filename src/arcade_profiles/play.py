"""Starting and ending a game under a profile's rules, and what the screen says.

Shared by the cabinet (gate_console, signin_console) and the simulator, so
both refuse, count and stop play the same way and show the same words.
"""

import datetime as dt
import subprocess

from .rules import decide, period_bounds, remaining_seconds, window_at

DISMISS_SECONDS = 10.0   # a refusal or time-up screen stays this long, or until a button


def network_time_synced():
    """True once the Pi has set its clock from the network (it has no battery clock, F-3)."""
    try:
        out = subprocess.run(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.stdout.decode().strip() == 'yes'


def clock_trusted(synced, wall, ledger):
    """DEC-1: trust the clock only once it is set from the network and has not
    gone back before a play already recorded."""
    latest = ledger.latest_start()
    return synced and (latest is None or wall >= latest)


def check(profiles, profile, wall, ledger, synced):
    """The rules' decision for starting a game at wall (epoch seconds)."""
    return decide(profiles, profile, dt.datetime.fromtimestamp(wall), ledger.plays(),
                  ledger.since, clock_trusted(synced, wall, ledger))


def play_seconds(decision, wall):
    """How long a game allowed by decision may run, or None for no limit."""
    if decision.until is None:
        return None
    return max(0.0, decision.until.timestamp() - wall)


def refresh_limit(profiles, ledger, wall, mono):
    """Hold the running game to its profile's hours and time as they are now,
    so a change the owner makes mid-game applies to it (M-3). A limit lowered
    below what was already played stops the game at once, and that time still
    counts. A profile the owner removed stops its game at once."""
    o = ledger.open
    if not o:
        return
    profile = next((p for p in profiles if p.id == o['profile']), None)
    elapsed = max(0.0, mono - o['start_mono'])
    # Time already played under the limit it had counts, even if the new one is lower.
    played = elapsed if o['limit'] is None else min(elapsed, o['limit'])
    if profile is None:
        o['limit'] = played
        return
    if profile.role == 'owner':
        o['limit'] = None
        return
    start = dt.datetime.fromtimestamp(o['start'])
    by_time = remaining_seconds(profile, start, ledger.data['plays'], ledger.since)
    window = window_at(profile.limits, dt.datetime.fromtimestamp(wall))
    by_hours = elapsed if window is None else elapsed + window[1].timestamp() - wall
    o['limit'] = max(played, min(by_time, by_hours))


# -- words -------------------------------------------------------------- #

def clock_time(t):
    hour = t.hour % 12 or 12
    return '%d:%02d %s' % (hour, t.minute, 'am' if t.hour < 12 else 'pm')


def when(t, now):
    days = (t.date() - now.date()).days
    if days == 0:
        day = 'today'
    elif days == 1:
        day = 'tomorrow'
    elif days < 7:
        day = t.strftime('%A')
    else:
        day = '%s %d %s' % (t.strftime('%a'), t.day, t.strftime('%b'))
    return '%s at %s' % (day, clock_time(t))


def minutes_text(seconds):
    if seconds < 60:
        return 'under 1 min'
    minutes = int((seconds + 30) // 60)
    if minutes < 60:
        return '%d min' % minutes
    return '%d h %02d min' % (minutes // 60, minutes % 60)


def period_text(limits):
    if limits.days == 1:
        return 'today'
    if limits.days == 7:
        return 'this week'
    return 'these %d days' % limits.days


def _hours_today(profile, now):
    ranges = profile.limits.hours[now.weekday()]
    if not ranges:
        return '%s has no play hours today' % profile.name
    midnight = dt.datetime.combine(now.date(), dt.time())
    spans = ['%s - %s' % (clock_time(midnight + dt.timedelta(minutes=s)),
                          clock_time(midnight + dt.timedelta(minutes=e)))
             for s, e in ranges]
    return '%s plays %s today' % (profile.name, ', '.join(spans))


def _next(decision, now):
    if decision.next_allowed is None:
        return 'No play allowed in the next few weeks'
    return 'Next play: %s' % when(decision.next_allowed, now)


def reason_lines(owner_name, decision, now):
    """Why play is refused, and when it is next allowed."""
    p = decision.profile
    if decision.reason == 'clock':
        return ['The clock is not set yet, so only %s can play.' % owner_name,
                'It sets itself from the network; check the cable.']
    if decision.reason == 'hours':
        return [_hours_today(p, now), _next(decision, now)]
    if decision.reason == 'used_up':
        return ["%s's %d min for %s are used up" % (p.name, p.limits.minutes, period_text(p.limits)),
                _next(decision, now)]
    if decision.reason == 'guest_blocked':
        b = decision.blocker
        return ["%s's time for %s is used up," % (b.name, period_text(b.limits)),
                'so no one can play as %s now' % p.name, _next(decision, now)]
    raise ValueError(decision.reason)


def _removed_line(session):
    name = (session or {}).get('name') or 'This'
    return "%s's profile was removed by the owner." % name


def not_signed_in_screen(session):
    """A game start with no profile signed in, or one the owner has removed."""
    if session:
        title, lines = 'Profile removed', [_removed_line(session)]
    else:
        title, lines = 'Nobody is signed in', []
    return {'view': 'refused', 'title': title,
            'lines': lines + ['Quit EmulationStation (Start, Quit) to sign in.',
                              '', 'The game did not start.', 'Press any button']}


def removed_screen(session):
    """Shown when a game was stopped because the owner removed its profile."""
    return {'view': 'timeup', 'title': 'Profile removed',
            'lines': [_removed_line(session), 'Quit EmulationStation (Start, Quit) to sign in.',
                      '', 'The game was stopped.', 'Press any button']}


TITLES = {'clock': 'Only the owner can play now', 'hours': 'Not play time',
          'used_up': 'Time is used up', 'guest_blocked': 'Guest play is paused'}


def _owner_name(profiles):
    return next(p.name for p in profiles if p.role == 'owner')


def refusal_screen(profiles, decision, wall):
    now = dt.datetime.fromtimestamp(wall)
    return {'view': 'refused', 'title': TITLES[decision.reason],
            'lines': reason_lines(_owner_name(profiles), decision, now)
            + ['', 'The game did not start.', 'Press any button']}


def status_lines(profiles, decision, wall):
    """What the welcome screen says about time left, right after sign-in."""
    now = dt.datetime.fromtimestamp(wall)
    if decision.allowed and decision.until is None:
        return ['No time limit']
    if decision.allowed:
        return ['Time left: %s (play until %s)' % (
            minutes_text(play_seconds(decision, wall)), clock_time(decision.until))]
    return [TITLES[decision.reason] + ':'] + reason_lines(_owner_name(profiles), decision, now)


def timeup_screen(profiles, profile, ledger, wall, synced):
    """Shown when a game was stopped because its time ran out."""
    now = dt.datetime.fromtimestamp(wall)
    decision = check(profiles, profile, wall, ledger, synced)
    left = remaining_seconds(profile, now, ledger.plays(), ledger.since)
    if left is not None and left < 60:
        first = "%s's %d min for %s are used up" % (
            profile.name, profile.limits.minutes, period_text(profile.limits))
    else:
        first = "%s's play hours are over" % profile.name
    lines = [first]
    if not decision.allowed:
        lines.append(_next(decision, now))
    return {'view': 'timeup', 'title': 'Time is up',
            'lines': lines + ['', 'The game was stopped.', 'Press any button']}


def usage_summary(profiles, ledger, wall):
    """Per profile: time used and left this period (simulator side panel)."""
    now = dt.datetime.fromtimestamp(wall)
    plays = ledger.plays()
    out = []
    for p in profiles:
        if p.role == 'owner':
            used = sum(x['seconds'] for x in plays if x['profile'] == p.id)
            out.append({'id': p.id, 'name': p.name, 'used': used, 'left': None, 'period': 'all time'})
            continue
        start, end = period_bounds(p.limits, now)
        used = sum(x['seconds'] for x in plays
                   if x['profile'] == p.id and start.timestamp() <= x['start'] < end.timestamp())
        out.append({'id': p.id, 'name': p.name, 'used': used,
                    'left': remaining_seconds(p, now, plays, ledger.since),
                    'period': period_text(p.limits)})
    return out
