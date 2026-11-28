# Pi Arcade

Single-player high-score arcade cabinet running on a Raspberry Pi 3 Model B.

**Hardware:** Pi 3B v1.2 · 4-way joystick · 8 buttons (6 action + Coin + Start) · breadboard
**Software:** RetroPie · MAME (lr-mame2003-plus) · Sega Genesis (lr-genesis-plus-gx) · NES (lr-fceumm) · SNES (lr-snes9x2010) · Game Boy Advance (lr-mgba) · custom GPIO daemon

---

## Quick Start

### 1. Flash RetroPie

Download the **RetroPie image for RPi 2/3** from [retropie.org.uk/download](https://retropie.org.uk/download/) and flash it to a microSD card with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (choose "Use custom") or [Balena Etcher](https://etcher.balena.io/). Boot the Pi and complete initial RetroPie setup.

### 2. Enable SSH on the Pi

In RetroPie, go to **RetroPie menu → raspi-config → Interface Options → SSH → Enable**.

Find the Pi's IP: `hostname -I` in a terminal on the Pi.

### 3. Deploy and install from your Mac

```bash
# Clone this repo
git clone <repo-url>
cd pi-arcade

# Set Pi address (default: pi@raspberrypi.local)
export PI_HOST=pi@<pi-ip-address>

# Push all files to the Pi and run the installer
make deploy-install
```

That's it. The installer handles dependencies, the GPIO daemon, and the RetroPie emulator setup.

### 4. Wire up the hardware

See [docs/hardware-setup.md](docs/hardware-setup.md) for the complete wiring guide.

Confirm your actual GPIO pins match [config/gpio_map.json](config/gpio_map.json) — a mismatched pin gives a dead input with no error.

### 5. Copy your ROMs

ROMs are **not included** and must be legally obtained — dumped from hardware you own, or from an official re-release. `make deploy` skips the `roms/` folder, so copy them to the Pi directly (see [RetroPie: Transferring ROMs](https://retropie.org.uk/docs/Transferring-Roms/)).

**MAME:** copy the ROM zips to `/home/pi/RetroPie/roms/mame-libretro/`. They must match **MAME 0.78 / mame2003-plus** — other versions will not load:

- [MAME free/legal ROMs](https://www.mamedev.org/roms/) — the officially redistributable sets
- [mame2003-plus compatibility list](https://docs.libretro.com/library/mame_2003_plus/) — which games this core runs
- [docs/games.md](docs/games.md) — the 10 games and their exact ROM filenames

**Sega Genesis:** copy `.md` / `.bin` / `.gen` / `.smd` / `.zip` ROMs to `/home/pi/RetroPie/roms/megadrive/`. See [docs/sega-genesis.md](docs/sega-genesis.md) for the game list, ROM filenames, and controls.

**NES:** copy `.nes` / `.zip` / `.7z` ROMs to `/home/pi/RetroPie/roms/nes/`. See [docs/nes.md](docs/nes.md).

**SNES:** copy `.sfc` / `.smc` / `.zip` / `.7z` ROMs to `/home/pi/RetroPie/roms/snes/`. See [docs/snes.md](docs/snes.md).

**Game Boy Advance:** copy `.gba` ROMs to `/home/pi/RetroPie/roms/gba/`. See [docs/gba.md](docs/gba.md).

**PlayStation:** copy `.cue` + `.bin` files to `/home/pi/RetroPie/roms/psx/` and the `scph1001.bin` BIOS to `/home/pi/RetroPie/BIOS/`. See [docs/psx.md](docs/psx.md).

**Arcade profiles:** players sign in with a button combo before playing, each profile plays only in its hours and for its time limit, and an idle sign-in screen shows each game's high score and who holds it. Off by default; manage profiles, score owners and the switch with `make admin`. See [docs/arcade-profiles.md](docs/arcade-profiles.md).

**Ports:** keyboard-only PC games (LBreakout2) run under a joystick-to-keyboard bridge. See [docs/ports.md](docs/ports.md).

### 6. Connect the TV and first boot

- Plug in **HDMI before powering on** — the Pi 3 only detects the display at boot; hotplug is unreliable.
- `sudo reboot` the Pi.
- On first boot, EmulationStation prompts to **configure a controller** — move the joystick and press the buttons as shown. Do this once or the menus won't respond to your panel. The GPIO daemon presents a virtual pad named `Pi Arcade Controller`.
- Pick a game and play. Inside MAME, **Coin** inserts a credit and **Start** begins play. Genesis, NES, SNES and GBA games start with **Start**; there are no credits.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `apt-get` fails: `buster Release no longer has a release file` | The RetroPie image ships EOL Raspbian Buster. Repoint the OS repo to the archive, then re-run the installer: `echo 'deb http://legacy.raspbian.org/raspbian/ buster main contrib non-free rpi' \| sudo tee /etc/apt/sources.list && sudo apt-get -o Acquire::Check-Valid-Until=false update` |
| Menus don't respond to the panel | Re-run controller config: EmulationStation → Start → **Configure Input** |
| An input does nothing | GPIO pin doesn't match `config/gpio_map.json`; check daemon log: `journalctl -u pi-arcade-gpio -f` |
| No sound over HDMI | Force HDMI audio in `raspi-config`, or set `hdmi_drive=2` in `/boot/config.txt` |
| Picture edges cut off | Adjust overscan in RetroPie → **Configuration → Video** |
| Game won't load | ROM set isn't MAME 0.78 / mame2003-plus |
| Genesis system is missing from EmulationStation | Re-run `make install` to install the core and create `/home/pi/RetroPie/roms/megadrive/` |
| Genesis game isn't listed | File extension isn't one of `.md`, `.bin`, `.gen`, `.smd`, `.zip` |
| NES / SNES system is missing from EmulationStation | The ROM folder is empty. EmulationStation hides systems with no games, so copy at least one ROM and restart EmulationStation |

---

## Project Structure

```
pi-arcade/
├── config/
│   ├── gpio_map.json        # GPIO pin assignments — edit this first
│   ├── cabinet.json         # cabinet feature flags (arcade-profiles.enforce)
│   ├── profiles.json        # arcade profiles as shipped (changed with make admin)
│   ├── hiscores.json        # where each game's top score is in its MAME hiscore save
│   └── retroarch-autoconfig/  # RetroArch profiles for the virtual pads
├── docs/
│   ├── hardware-setup.md    # Wiring diagrams and physical assembly
│   ├── games.md             # MAME game list, controls, ROM filenames
│   ├── sega-genesis.md      # Genesis game list, controls, ROM filenames
│   ├── nes.md               # NES game list and controls
│   ├── snes.md              # SNES game list and controls
│   └── gba.md               # GBA game list, controls, performance
├── scripts/
│   ├── install.sh           # Runs on the Pi — installs everything
│   └── deploy.sh            # Runs on your Mac — rsync to Pi
├── src/
│   ├── gpio_daemon.py       # GPIO → virtual gamepad daemon
│   └── arcade_profiles/     # combo sign-in, hours and time limits (docs/arcade-profiles.md)
├── admin/                   # arcade profiles admin, on the owner's computer (make admin)
├── sim/                     # browser cabinet simulator (make sim)
├── systemd/
│   └── pi-arcade-gpio.service
└── Makefile
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make deploy` | rsync project to Pi |
| `make install` | run install.sh on Pi via SSH |
| `make deploy-install` | deploy then install |
| `make ssh` | open SSH session to Pi |
| `make gpio-test` | run GPIO daemon in test/verbose mode |
| `make logs` | tail GPIO daemon logs |
| `make test` | run the unit tests locally |
| `make sim` | cabinet simulator at http://127.0.0.1:21000 (arcade profiles on) |
| `make sim-flag-off` | the simulator with the shipped flag (off) |
| `make admin` | arcade profiles admin at http://127.0.0.1:21010, for the cabinet at `PI_HOST` |
| `make admin-sim` | the admin for the simulator's cabinet (run `make sim` first) |

Set `PI_HOST` to override the default (`pi@raspberrypi.local`):

```bash
make deploy PI_HOST=pi@192.168.1.42
```
