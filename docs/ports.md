# Ports (native PC games)

The **Ports** system in EmulationStation lists games that run natively on the Pi rather than in an emulator. These games only read the keyboard, so each one launches through `src/keybridge.py`. While the game runs, the bridge turns the panel's virtual gamepad into keystrokes using the game's `config/ports/<id>/keymap.json`.

`scripts/install.sh` installs each port, writes its launcher to `/home/pi/RetroPie/roms/ports/`, writes its `runcommand` entry to `/opt/retropie/configs/ports/<id>/emulators.cfg`, and adds the Ports system to `es_systems.cfg` if it's missing. It also gives the `input` group write access to `/dev/uinput`, so the bridge can create its virtual keyboard without root.

**Exit any port:** hold **Coin + Start**, the same combo as RetroArch.

---

## LBreakout2

A free, open-source brick breaker (Debian package `lbreakout2`). It starts fullscreen from a seeded `~/.lgames/lbreakout2.conf`, which is only written if that file doesn't exist yet, so settings changed in the game are kept.

| Physical input | LBreakout2 |
|----------------|------------|
| Joystick left / right | Move the paddle |
| Joystick up / down | Navigate menus |
| BTN 1 | Fire / launch ball (Space) |
| BTN 2 | Fire left (Y); also "yes" in dialogs |
| BTN 3 | Paddle turbo (X) |
| BTN 4 | Return a stuck ball (Backspace) |
| BTN 5 | Warp to next level once allowed (W) |
| BTN 6 | "No" in dialogs (N) |
| Start | Menu select (Enter) |
| Coin | Back / pause menu (Esc) |

---

## Adding a port

1. Install the game's binary in `scripts/install.sh`.
2. Add `config/ports/<id>/keymap.json`. Button names come from `config/gpio_map.json` (`BTN_SOUTH` … `BTN_START`). Key names are evdev `KEY_*` names.
3. Add `"<id>|<Menu Title>|<command>"` to the `PORTS` list in `scripts/install.sh`, then run the installer.
4. Restart EmulationStation from its Start menu so it picks up the new entry.

Tests for the bridge run on the Pi: `python3 -m unittest discover -s tests`.
