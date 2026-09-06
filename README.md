# Pi Arcade

Single-player high-score arcade cabinet running on a Raspberry Pi 3 Model B.

**Hardware:** Pi 3B v1.2 · 4-way joystick · 8 buttons (6 action + Coin + Start) · breadboard
**Software:** RetroPie · MAME (lr-mame2003-plus) · custom GPIO daemon

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

That's it. The installer handles dependencies, the GPIO daemon, and the RetroPie MAME setup.

### 4. Wire up the hardware

See [docs/hardware-setup.md](docs/hardware-setup.md) for the complete wiring guide.

Confirm your actual GPIO pins match [config/gpio_map.json](config/gpio_map.json) — a mismatched pin gives a dead input with no error.

### 5. Copy your ROMs

ROMs are **not included** and must be legally obtained — dumped from hardware you own, or from an official re-release. Copy the MAME ROM zips to `/home/pi/RetroPie/roms/mame-libretro/` on the Pi (see [RetroPie: Transferring ROMs](https://retropie.org.uk/docs/Transferring-Roms/)).

They must match **MAME 0.78 / mame2003-plus** — other versions will not load:

- [MAME free/legal ROMs](https://www.mamedev.org/roms/) — the officially redistributable sets
- [mame2003-plus compatibility list](https://docs.libretro.com/library/mame_2003_plus/) — which games this core runs
- [docs/games.md](docs/games.md) — the 10 games and their exact ROM filenames

### 6. Connect the TV and first boot

- Plug in **HDMI before powering on** — the Pi 3 only detects the display at boot; hotplug is unreliable.
- `sudo reboot` the Pi.
- On first boot, EmulationStation prompts to **configure a controller** — move the joystick and press the buttons as shown. Do this once or the menus won't respond to your panel. The GPIO daemon presents a virtual pad named `Pi Arcade Controller`.
- Pick a game and play. Inside MAME, **Coin** inserts a credit and **Start** begins play.

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

---

## Project Structure

```
pi-arcade/
├── config/
│   └── gpio_map.json        # GPIO pin assignments — edit this first
├── docs/
│   ├── hardware-setup.md    # Wiring diagrams and physical assembly
│   └── games.md             # Game list, controls, ROM filenames
├── scripts/
│   ├── install.sh           # Runs on the Pi — installs everything
│   └── deploy.sh            # Runs on your Mac — rsync to Pi
├── src/
│   └── gpio_daemon.py       # GPIO → virtual gamepad daemon
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

Set `PI_HOST` to override the default (`pi@raspberrypi.local`):

```bash
make deploy PI_HOST=pi@192.168.1.42
```
