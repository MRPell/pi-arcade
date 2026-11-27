"""Play hours and time limits: may a profile start a game now, and until when.

Pure functions over naive local datetimes and the play records from
arcade_profiles.usage, so the cabinet and the simulator decide the same way.

Rules, per profile in config/profiles.json:

    "limits": {
      "hours": {"weekdays": "15:00-20:00", "weekends": "09:00-20:00"},
      "time":  {"minutes": 60, "per": "day", "rollover": false}
    }

- hours: keys weekdays (Mon-Fri), weekends (Sat, Sun) or a day (mon ... sun,
  which wins over its group); a value is "HH:MM-HH:MM", a list of them, or []
  for no play that day. A day with no key has no play.
- time.per: "day", "week" (Monday to Sunday) or "N days" with "from":
  "YYYY-MM-DD", the first day of the first N-day stretch.
- time.rollover: the part of the last period's allowance left unused is added
  to this period's (only one period back, so at most double).

The owner has no limits. The guest has its own limits, and also cannot play
while any player's time is used up, so guest play never adds time for a
player (MH-2). With an untrustworthy clock only the owner plays (DEC-1).
"""

import datetime as dt
import re
from collections import namedtuple

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
GROUPS = {'weekdays': DAYS[:5], 'weekends': DAYS[5:]}
# A game may only start with at least this much play left.
MIN_START_SECONDS = 60
SEARCH_DAYS = 60
WEEK_ANCHOR = dt.date(2024, 1, 1)  # a Monday

Limits = namedtuple('Limits', 'hours minutes days anchor rollover')
Decision = namedtuple('Decision', 'allowed reason profile blocker until next_allowed')
Decision.__new__.__defaults__ = (None, None, None, None)

_RANGE = re.compile(r'^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$')
_PER_DAYS = re.compile(r'^(\d+) days$')


class LimitsError(ValueError):
    pass


# -- parsing ------------------------------------------------------------- #

def _minutes(h, m, pid):
    h, m = int(h), int(m)
    if m > 59 or h > 24 or (h == 24 and m):
        raise LimitsError('%s: bad time %02d:%02d' % (pid, h, m))
    return h * 60 + m


def _ranges(pid, value):
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list):
        raise LimitsError('%s: hours must be "HH:MM-HH:MM" or a list of them' % pid)
    out = []
    for v in values:
        match = _RANGE.match(v.strip()) if isinstance(v, str) else None
        if not match:
            raise LimitsError('%s: bad hours %r (want "HH:MM-HH:MM")' % (pid, v))
        start = _minutes(match.group(1), match.group(2), pid)
        end = _minutes(match.group(3), match.group(4), pid)
        if end <= start:
            raise LimitsError('%s: hours %r end before they start' % (pid, v))
        out.append((start, end))
    return sorted(out)


def parse_limits(pid, raw):
    if not isinstance(raw, dict) or 'hours' not in raw or 'time' not in raw:
        raise LimitsError('%s: limits need "hours" and "time"' % pid)

    hours = {d: [] for d in range(7)}
    spec = raw['hours']
    for key in spec:
        if key not in GROUPS and key not in DAYS:
            raise LimitsError('%s: unknown hours key %r' % (pid, key))
    for group, days in GROUPS.items():
        if group in spec:
            for d in days:
                hours[DAYS.index(d)] = _ranges(pid, spec[group])
    for d in DAYS:
        if d in spec:
            hours[DAYS.index(d)] = _ranges(pid, spec[d])

    time = raw['time']
    minutes = time.get('minutes')
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
        raise LimitsError('%s: time.minutes must be a whole number of minutes' % pid)
    per = time.get('per')
    anchor = None
    if per == 'day':
        days, anchor = 1, WEEK_ANCHOR
    elif per == 'week':
        days, anchor = 7, WEEK_ANCHOR
    else:
        match = _PER_DAYS.match(per) if isinstance(per, str) else None
        if not match or int(match.group(1)) < 1:
            raise LimitsError('%s: time.per must be "day", "week" or "N days"' % pid)
        days = int(match.group(1))
        try:
            anchor = dt.datetime.strptime(time.get('from', ''), '%Y-%m-%d').date()
        except ValueError:
            raise LimitsError('%s: time.per "N days" needs "from": "YYYY-MM-DD"' % pid)
    rollover = time.get('rollover', False)
    if not isinstance(rollover, bool):
        raise LimitsError('%s: time.rollover must be true or false' % pid)
    return Limits(hours, minutes, days, anchor, rollover)


# -- periods and time left ---------------------------------------------- #

def period_bounds(limits, now):
    """The (start, end) of the period that now falls in."""
    k = (now.date() - limits.anchor).days // limits.days
    start = dt.datetime.combine(limits.anchor + dt.timedelta(days=k * limits.days), dt.time())
    return start, start + dt.timedelta(days=limits.days)


def _used(pid, plays, start, end):
    lo, hi = start.timestamp(), end.timestamp()
    return sum(p['seconds'] for p in plays if p['profile'] == pid and lo <= p['start'] < hi)


def allowance_seconds(profile, now, plays, since):
    limits = profile.limits
    base = limits.minutes * 60
    if not limits.rollover:
        return base
    start, _ = period_bounds(limits, now)
    prev = start - dt.timedelta(days=limits.days)
    # Only a period that was counted can leave time over.
    if since is None or start.timestamp() <= since:
        return base
    return base + max(0, base - _used(profile.id, plays, prev, start))


def remaining_seconds(profile, now, plays, since):
    """Play time left in the current period; None for the owner (no limit)."""
    if profile.role == 'owner':
        return None
    start, end = period_bounds(profile.limits, now)
    return max(0, allowance_seconds(profile, now, plays, since) - _used(profile.id, plays, start, end))


def window_at(limits, now):
    """The (start, end) datetimes of the play window now is in, or None."""
    minute = now.hour * 60 + now.minute + now.second / 60.0
    midnight = dt.datetime.combine(now.date(), dt.time())
    for start, end in limits.hours[now.weekday()]:
        if start <= minute < end:
            return midnight + dt.timedelta(minutes=start), midnight + dt.timedelta(minutes=end)
    return None


# -- the decision ------------------------------------------------------- #

def _decide_now(profiles, profile, now, plays, since):
    window = window_at(profile.limits, now)
    if window is None:
        return Decision(False, 'hours', profile)
    left = remaining_seconds(profile, now, plays, since)
    if left < MIN_START_SECONDS:
        return Decision(False, 'used_up', profile)
    if profile.role == 'guest':
        for p in profiles:
            if p.role == 'player' and remaining_seconds(p, now, plays, since) < MIN_START_SECONDS:
                return Decision(False, 'guest_blocked', profile, blocker=p)
    return Decision(True, None, profile, until=min(now + dt.timedelta(seconds=left), window[1]))


def _candidates(profiles, profile, now):
    """Every moment after now when the answer could change, given no more play:
    a play window opening or a period starting."""
    watched = [profile] + ([p for p in profiles if p.role == 'player']
                           if profile.role == 'guest' else [])
    out = set()
    today = now.date()
    for offset in range(SEARCH_DAYS + 1):
        day = today + dt.timedelta(days=offset)
        midnight = dt.datetime.combine(day, dt.time())
        for p in watched:
            for start, _ in p.limits.hours[day.weekday()]:
                out.add(midnight + dt.timedelta(minutes=start))
            if period_bounds(p.limits, midnight)[0] == midnight:
                out.add(midnight)
    return sorted(t for t in out if t > now)


def decide(profiles, profile, now, plays, since, clock_trusted):
    """May this profile start a game at now (a naive local datetime)?

    Allowed decisions carry `until`: when the game must stop (None = never).
    Refusals carry `reason` (hours, used_up, guest_blocked, clock) and
    `next_allowed`, the first moment play is allowed again (None if not
    within SEARCH_DAYS, or the clock cannot be trusted).
    """
    if profile.role == 'owner':
        return Decision(True, None, profile)
    if not clock_trusted:
        return Decision(False, 'clock', profile)
    decision = _decide_now(profiles, profile, now, plays, since)
    if decision.allowed:
        return decision
    for t in _candidates(profiles, profile, now):
        if _decide_now(profiles, profile, t, plays, since).allowed:
            return decision._replace(next_allowed=t)
    return decision
