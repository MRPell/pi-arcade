# Arcade profiles

Players sign in at the cabinet with their own button combo before
EmulationStation starts, and each profile can then start games only inside its
play hours and while it has time left. It ships dark: nothing changes until the
`arcade-profiles.enforce` flag is on.

Built so far: sign-in (M-1), hours and time limits (M-2), and the admin on
the owner's computer (M-3). The high-score screen comes in a later milestone.

## The flag

`config/cabinet.json` on the Pi:

```json
{ "arcade-profiles.enforce": false }
```

- **Off** (default, and if the file is missing or broken): the cabinet boots
  straight into EmulationStation and plays exactly as before.
- **On**: the sign-in screen comes first, and games are held to the signed-in
  profile's hours and time limit. Quitting EmulationStation
  (Start → Quit → Quit EmulationStation) goes back to sign-in for the next player.

Turn it on or off from the admin on your computer (below). The cabinet reads it
each time EmulationStation quits, both ways, so a change takes effect at the
next quit with no restart: turned on, the next quit goes to sign-in; turned
off, the next quit drops to the console, as quitting did before profiles.
Mid-session nothing changes.

## Profiles and combos

`config/profiles.json` holds the shipped profiles: Matt (owner), Theo, John and
Guest. Change them from the admin on your computer (below); nothing at the
cabinet can change them.

| Profile | Combo (shipped default — change these) |
|---------|------|
| Matt  | Up, Up, Down, Down, 1, 2 |
| Theo  | Left, Right, Left, Right, 1 |
| John  | Right, Left, Right, Left, 2 |
| Guest | Start |

Rules, checked when the sign-in screen loads:

- A combo is up to 8 inputs pressed one after another: joystick directions, buttons 1–6, Start.
- Coin is never part of a combo. On the sign-in screen, Coin starts the combo again.
- No combo may be the start of another, since a combo signs in the moment it is complete.

## Hours and time limits

Each profile but the owner's has `limits` in `config/profiles.json`:

```json
"limits": { "hours": { "weekdays": "15:00-20:00", "weekends": "09:00-20:00" },
            "time":  { "minutes": 60, "per": "day", "rollover": false } }
```

- **hours**: `weekdays` (Mon–Fri), `weekends` (Sat, Sun), or a single day
  (`mon` … `sun`, which wins over its group). A value is `"HH:MM-HH:MM"`, a list
  of them, or `[]` for no play. A day not listed has no play.
- **time.minutes** per **time.per**: `"day"`, `"week"` (Monday to Sunday) or
  `"N days"` with `"from": "YYYY-MM-DD"`, the first day of the first N-day stretch.
- **time.rollover**: `true` adds what was left unused of the last period's
  minutes to this period (one period back only, so at most double).

Shipped: Theo and John 60 minutes a day, Guest 30 minutes a day, all 3–8 pm on
school days and 9 am–8 pm at weekends. Matt (owner) has no limits.

What the cabinet does:

- **Starting a game** checks the signed-in profile. Outside its hours, or with
  less than a minute left, the game does not start; the screen says why and when
  play is next allowed, for 10 seconds or until a button is pressed.
- **During a game** time is counted, and the game is stopped when the time left
  runs out or the play hours end, whichever is first; the screen says "Time is up".
- Time counts from game start to game end, over every game and sign-in in the
  period. It is kept in `/home/pi/.pi-arcade/usage.json` and survives a reboot or
  power cut (losing at most 15 seconds).
- **Guest** has its own 30 minutes, and cannot play at all while Theo's or John's
  time is used up, so a player out of time gets nothing more by signing in as
  Guest. Guest plays again when that player's next period starts (for a daily
  limit, the next play hours).
- **Clock**: the Pi has no battery clock. Until it has set the time from the
  network (`timedatectl` says NTP synchronised), or if the clock reads earlier
  than the last game played, only the owner can play.
- The welcome screen after sign-in says the time left and until when, or why
  play is not allowed now.

Change them from the admin (below). A change applies to the next game, and to
a game already running within 15 seconds: raised, it plays on; lowered below
what was already played, it stops with "Time is up" and the time played
still counts.

## At the cabinet

1. "Who is playing?" Enter your combo; a `*` appears per input.
2. A wrong combo says "Combo not recognised. Try again." Stopping for 5 seconds also starts over.
3. "Signed in: Theo", with the time left (or why play isn't allowed now). Press
   any button to play.

Combos are read only on the sign-in screen, which is not running while
EmulationStation or a game is, so a combo never fires inside a game. Anything
pressed together with Coin (the Coin + Start exit chord, Coin hotkeys) is ignored.

Who is signed in is kept in `/home/pi/.pi-arcade/session.json`.

## Admin, from the owner's computer

```bash
make admin PI_HOST=pi@retropie.local      # then open http://127.0.0.1:21010
```

The admin page shows what the cabinet has and changes it:

- **Profile enforcement**: turn `arcade-profiles.enforce` on or off.
- **Profiles**: each profile's name, combo (pressed into the page with the
  cabinet's inputs), play hours (weekdays, weekends, or one day different) and
  time limit (minutes per day, week or N days, with rollover). Add a player or
  remove one. **Save to cabinet** checks the change first; a combo that clashes,
  hours that end before they start, a missing owner or the like is refused with
  the reason, and the cabinet keeps what it had.

It reaches the cabinet over SSH (the computer needs passwordless SSH to the
Pi) and runs `python3 -m arcade_profiles.settings` there, which checks the
change again and writes it to `/home/pi/.pi-arcade/cabinet.json` and
`profiles.json`. Those win over the shipped `config/` files and are outside the
repo copy, so `make deploy` never undoes them. The admin listens on
127.0.0.1 only, so no other device on the network can reach it, and the
cabinet's controls have no way to change any of this. Deploy this version to
the Pi first (`make deploy`).

- Combos: the sign-in screen picks up a change while it is showing.
- Removing a player signs them out at once: on the welcome screen they are back
  at sign-in, at the game list their next game is refused ("Profile removed"),
  and a game they are playing is stopped within 15 seconds.
- Hours and time limits: the next game, and a running game within 15 seconds.
- The flag: the next time EmulationStation quits.

## Install

`make deploy-install` hooks `scripts/arcade-session.sh` into
`/opt/retropie/configs/all/autostart.sh` (the original is saved as
`autostart.sh.pre-profiles`). With the flag off the script runs
`emulationstation` as the original line did; when it quits, the script checks
the flag once more and, unless the owner turned it on meanwhile, ends there
with EmulationStation's exit status, as before.

It also links `scripts/runcommand-onstart.sh` and `runcommand-onend.sh` into
`/opt/retropie/configs/all/`, which RetroPie's runcommand runs before and after
every game. They do nothing unless EmulationStation was started by
`arcade-session.sh` with the flag on (it sets `ARCADE_PROFILES_ENFORCED=1`), so
with the flag off games launch exactly as before. If either file already exists
and is not a link, the installer leaves it alone and warns.

## Simulator

`make sim`, then open http://127.0.0.1:21000. It runs the same sign-in and
play-rules code in front of a stand-in EmulationStation. `make sim-flag-off` uses
the shipped config (flag off). Keyboard: arrows, 1–6, Shift = Coin, Enter = Start.

`make admin-sim` (in a second terminal, after `make sim`) runs the admin
against the simulator's cabinet at http://127.0.0.1:21010, through the same
settings command the Pi runs. The simulator keeps its cabinet's settings in
`.sim-cabinet/` (`SIM_DIR`); each start of `make sim` resets them from
`config/` and forgets every play, and a power-cycle keeps them. To run both
simulators at once, give the second its own `SIM_DIR` and `PORT`, and point
`make admin-sim` at it with the same `SIM_DIR` and another `ADMIN_PORT`.

The side panel (simulator only) sets the cabinet clock, lets time pass (+1 min,
+10 min, +1 hour, which also counts toward a running game), turns network time
sync off and on, and shows each profile's time used and left. It starts at the
real time with a fresh, empty play record each run. Setting the clock earlier
than a game already played makes the clock untrusted (only the owner plays),
as on the cabinet; **Clear play record and power-cycle** starts over.
