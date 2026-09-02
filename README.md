# Pi Arcade

Single-player high-score arcade cabinet running on a Raspberry Pi 3 Model B.

**Hardware:** Pi 3B v1.2 · 4-way joystick · 3 buttons · breadboard
**Software:** RetroPie · MAME (lr-mame2003-plus) · custom GPIO daemon

---

## Quick Start

### 1. Flash RetroPie

Download the RetroPie image for Pi 3 and flash it to a microSD card with Raspberry Pi Imager or Balena Etcher. Boot the Pi and complete initial RetroPie setup.

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

### 5. Copy your ROMs

ROMs are not included. Copy MAME ROM zips to `/home/pi/RetroPie/roms/mame-libretro/` on the Pi.

See [docs/games.md](docs/games.md) for the 10 games and their exact ROM filenames.

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
