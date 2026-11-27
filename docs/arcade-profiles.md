# Arcade profiles

Players sign in at the cabinet with their own button combo before
EmulationStation starts. It ships dark: nothing changes until the
`arcade-profiles.enforce` flag is on.

This is milestone M-1 (sign-in only). Hours, time limits, the admin tools and
the high-score screen come in later milestones.

## The flag

`config/cabinet.json` on the Pi:

```json
{ "arcade-profiles.enforce": false }
```

- **Off** (default, and if the file is missing or broken): the cabinet boots
  straight into EmulationStation and plays exactly as before.
- **On**: the sign-in screen comes first. Quitting EmulationStation
  (Start → Quit → Quit EmulationStation) goes back to sign-in for the next player.

Change it on your computer, then `make deploy PI_HOST=pi@retropie.local`. It is read
each time EmulationStation quits, or at the next boot.

## Profiles and combos

`config/profiles.json` holds the profiles: Matt (owner), Theo, John and Guest.
Edit it on your computer and deploy; nothing at the cabinet can change it.

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

## At the cabinet

1. "Who is playing?" Enter your combo; a `*` appears per input.
2. A wrong combo says "Combo not recognised. Try again." Stopping for 5 seconds also starts over.
3. "Signed in: Theo". Press any button to play.

Combos are read only on the sign-in screen, which is not running while
EmulationStation or a game is, so a combo never fires inside a game. Anything
pressed together with Coin (the Coin + Start exit chord, Coin hotkeys) is ignored.

Who is signed in is kept in `/home/pi/.pi-arcade/session.json`.

## Install

`make deploy-install` hooks `scripts/arcade-session.sh` into
`/opt/retropie/configs/all/autostart.sh` (the original is saved as
`autostart.sh.pre-profiles`). With the flag off the script just runs
`emulationstation`, as the original line did.

## Simulator

`make sim`, then open http://127.0.0.1:21000. It runs the same sign-in code in
front of a stand-in EmulationStation. `make sim-flag-off` uses the shipped
config (flag off). Keyboard: arrows, 1–6, Shift = Coin, Enter = Start.
