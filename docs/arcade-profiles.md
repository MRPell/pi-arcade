# Arcade profiles

Players sign in at the cabinet with their own button combo before
EmulationStation starts, and each profile can then start games only inside its
play hours and while it has time left. It ships dark: nothing changes until the
`arcade-profiles.enforce` flag is on.

Built: sign-in (M-1), hours and time limits (M-2), the admin on the owner's
computer (M-3), the high-score screen with score owners (M-4), and the launch
checks for turning it on at the real cabinet (M-5, see Launch below).

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

## High scores

With the flag on, a sign-in screen left alone for 30 seconds (nothing entered)
turns into the high-score screen: one game at a time, every 5 seconds, its top
score and the profile that holds it ("Held by Theo", or "Held by no profile").
Any button brings sign-in back; that press is not part of a combo. With no high
scores yet, sign-in stays up. With the flag off there is no sign-in screen and
so no high-score screen: the cabinet behaves as before.

Where the scores come from: the games keep their own. The cabinet's MAME core
(lr-mame2003, RetroPie's default for `mame-libretro`) saves each game's
high-score table to `/home/pi/RetroPie/roms/mame-libretro/mame2003/hi/<game>.hi`
when the game exits; a game switched to lr-mame2003-plus in the runcommand menu
saves to `.../mame2003-plus/hi/` instead, and the cabinet reads whichever save
was written last. `config/hiscores.json` says where the top score is in that
file for Pac-Man, Galaga, Donkey Kong and Space Invaders; the positions were
checked against the cabinet's own saves (copies in `tests/fixtures/mame2003-hi`).
Other games show no high score until they are added there. Before each game the
cabinet reads the top scores; after it, a top score that changed is credited to
the profile that just played. A top score that changed while the flag was off
(including every score already on the cabinet at launch) is noted with no
profile at the first game start, for the owner to give to someone in the admin.
Who holds what is kept in `/home/pi/.pi-arcade/scores.json`.

Not yet checked on the cabinet: that a game stopped because time ran out still
saves its table.

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
- **High scores**: each game's top score and who holds it. Pick a different
  profile (or No profile) and it saves to the cabinet at once; the high-score
  screen shows it on its next turn. **Reload from cabinet** picks up scores set
  since the page was opened.

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

## Launch (M-5)

Turning it on at the real cabinet. Steps 1–3 change nothing players see while
the flag is off; step 4 is the switch.

1. `make test-pi`: runs every test on the cabinet's own Python (3.7) from a
   copy in `/tmp`, removed afterwards; the cabinet's install is untouched.
2. `make deploy-install`: copies this checkout to the cabinet and hooks
   arcade-session.sh and the game hooks in (above). With the flag off the
   cabinet still plays as before.
3. `make preflight`: changes nothing; checks the cabinet is ready and says what
   to fix. Each line is `ok`, `FAIL` with what to do, or `info`:
   - **cabinet / deployed**: reachable over SSH, and running this checkout.
   - **autostart / game hooks**: what `make install` sets up.
   - **controls**: the panel's pad is there, so players can sign in.
   - **sign-in font**: the large console font for reading from across the room.
   - **clock**: set from the network (until it is, only the owner can play).
   - **time zone**: the cabinet's is this computer's. Play hours are the
     cabinet's clock hours, so a cabinet on another time zone opens and closes
     play at the wrong time. The fix it prints is
     `sudo timedatectl set-timezone <yours>`, run on the cabinet (`make ssh`).
   - **high scores**: the MAME saves it found and their top scores.
   - **profiles / flag**: what the cabinet will use, and whether the flag is on.
   Run it again until nothing fails.
4. `make admin`, open http://127.0.0.1:21010 and turn **Profile enforcement**
   on. At the cabinet, quit EmulationStation once (Start → Quit → Quit
   EmulationStation): sign-in comes up and stays from then on, through reboots.
5. Walk it at the cabinet: each player signs in with their combo and sees their
   time left; a game outside the hours or with no time left is refused; Guest is
   paused while a boy is out of time; a change in the admin reaches the screen
   already up; the high-score screen comes up after 30 seconds idle; give the
   launch-day scores (held by no profile) to their players in the admin.

To switch it back off at any time: **Profile enforcement** off in the admin,
then quit EmulationStation once; the cabinet plays as before profiles.

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

The stand-in games score points (Button 1: 100, Button 2: 1,000) for Pac-Man,
Galaga, Donkey Kong and Space Invaders, up to the most each game's save holds
(9,999 for Space Invaders), and on exit save a new top score to
`hi/` in the simulator's cabinet the way the MAME core does; the real
high-score code reads it from there. The side panel lists the high scores and
who holds each. Each start of `make sim` clears them.
